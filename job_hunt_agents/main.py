"""Orchestrator for the multi-agent job hunt pipeline.

Usage:
    python main.py
    python main.py --role "Head of Data" --location "London" --industry "Real Estate"
    python main.py --batch

See README.md for full setup instructions.
"""

import argparse
import csv
import logging
import os
import sys
from datetime import date
from typing import List, Optional, Tuple

import config
from agents.auditor import run_auditor
from agents.scout import run_scout
from agents.strategist import run_strategist
from agents.surgeon import run_surgeon
from schemas import AuditReport, RewrittenResume, ScoutReport, StrategyReport
from utils.anthropic_client import dump_json
from utils.doc_writer import write_resume_docx
from utils.job_scraper import JobListing, search_jobs
from utils.resume_parser import parse_resume

logger = logging.getLogger("job_hunt_agents")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def slugify(text: str) -> str:
    """Turn arbitrary text into a filesystem-safe slug."""
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in text)
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_") or "unknown"


def run_pipeline_for_resume(
    resume_text: str, scout_report: ScoutReport
) -> Tuple[RewrittenResume, AuditReport, StrategyReport]:
    """Run Strategist -> Surgeon -> Auditor, retrying the Surgeon on failure.

    Args:
        resume_text: The candidate's original resume text.
        scout_report: The ScoutReport to tailor against.

    Returns:
        Tuple of (final RewrittenResume, final AuditReport, StrategyReport).
        The resume returned is the best attempt even if never approved, so
        a result is always produced within MAX_SURGEON_RETRIES + 1 attempts.
    """
    strategy_report = run_strategist(resume_text, scout_report)

    rewritten_resume = run_surgeon(resume_text, strategy_report, scout_report)
    audit_report = run_auditor(rewritten_resume, scout_report)

    attempt = 0
    while not audit_report.approved and attempt < config.MAX_SURGEON_RETRIES:
        attempt += 1
        logger.info(
            "[Orchestrator] Audit not approved (score %d/%d). Retry %d/%d...",
            audit_report.overall_score,
            config.MIN_ATS_SCORE,
            attempt,
            config.MAX_SURGEON_RETRIES,
        )
        rewritten_resume = run_surgeon(
            resume_text,
            strategy_report,
            scout_report,
            fix_instructions=audit_report.issues_found,
        )
        audit_report = run_auditor(rewritten_resume, scout_report)

    return rewritten_resume, audit_report, strategy_report


def print_summary(
    job_label: str,
    strategy_report,
    audit_report: AuditReport,
    output_path: str,
) -> None:
    print("\n" + "=" * 60)
    print(f"SUMMARY: {job_label}")
    print("=" * 60)
    print(f"  ATS score (Strategist, pre-rewrite):  {strategy_report.ats_score}/100")
    print(f"  Overall score (Auditor, final):        {audit_report.overall_score}/100")
    print(f"  Keyword coverage:                      {audit_report.keyword_coverage_score}%")
    print(f"  Approved:                               {audit_report.approved}")
    if strategy_report.gaps:
        print("  Top gaps found:")
        for gap in strategy_report.gaps[:5]:
            print(f"    - {gap}")
    if not audit_report.approved and audit_report.issues_found:
        print("  Remaining issues:")
        for issue in audit_report.issues_found[:5]:
            print(f"    - {issue}")
    print(f"  Saved to: {output_path}")
    print("=" * 60 + "\n")


def run_single_mode(
    resume_text: str, listings: List[JobListing], scout_report: ScoutReport, role: str, industry: str
) -> None:
    """Produce one tailored resume against the aggregate ScoutReport."""
    rewritten_resume, audit_report, strategy_report = run_pipeline_for_resume(
        resume_text, scout_report
    )

    dump_json(strategy_report, os.path.join(config.DATA_DIR, "strategy_report.json"))

    os.makedirs(config.OUTPUTS_DIR, exist_ok=True)
    filename = f"{slugify(role)}_{slugify(industry)}_{date.today().isoformat()}.docx"
    output_path = os.path.join(config.OUTPUTS_DIR, filename)
    write_resume_docx(rewritten_resume, output_path)

    print_summary(f"{role} ({industry})", strategy_report, audit_report, output_path)


def run_batch_mode(
    resume_text: str, listings: List[JobListing], scout_report: ScoutReport
) -> None:
    """Run the full pipeline once per job listing and write a summary CSV."""
    os.makedirs(config.OUTPUTS_DIR, exist_ok=True)
    csv_path = os.path.join(config.OUTPUTS_DIR, "batch_summary.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            ["job_title", "company", "url", "ats_score", "keyword_coverage", "approved"]
        )

        for i, listing in enumerate(listings, start=1):
            logger.info(
                "[Batch %d/%d] Tailoring resume for %s at %s...",
                i,
                len(listings),
                listing.title,
                listing.company,
            )
            try:
                rewritten_resume, audit_report, strategy_report = run_pipeline_for_resume(
                    resume_text, scout_report
                )
            except Exception:
                logger.exception(
                    "[Batch %d/%d] Failed to process listing '%s' at '%s'; skipping.",
                    i,
                    len(listings),
                    listing.title,
                    listing.company,
                )
                writer.writerow(
                    [listing.title, listing.company, listing.url, "", "", False]
                )
                continue

            job_dir = os.path.join(
                config.OUTPUTS_DIR, f"{slugify(listing.company)}_{slugify(listing.job_id)}"
            )
            os.makedirs(job_dir, exist_ok=True)
            output_path = os.path.join(job_dir, "resume.docx")
            write_resume_docx(rewritten_resume, output_path)

            writer.writerow(
                [
                    listing.title,
                    listing.company,
                    listing.url,
                    audit_report.overall_score,
                    audit_report.keyword_coverage_score,
                    audit_report.approved,
                ]
            )
            print_summary(
                f"{listing.title} @ {listing.company}",
                strategy_report,
                audit_report,
                output_path,
            )

    logger.info("[Batch] Summary CSV written to %s", csv_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-agent job hunt orchestrator")
    parser.add_argument("--role", default=config.TARGET_ROLE, help="Target job title")
    parser.add_argument("--location", default=config.TARGET_LOCATION, help="Target location")
    parser.add_argument("--industry", default=config.TARGET_INDUSTRY, help="Target industry")
    parser.add_argument("--resume", default=config.RESUME_PATH, help="Path to resume PDF/DOCX")
    parser.add_argument(
        "--max-listings",
        type=int,
        default=config.MAX_LISTINGS_TO_FETCH,
        help="Maximum number of job listings to fetch",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run the full pipeline once per job listing instead of once overall",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()

    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs(config.OUTPUTS_DIR, exist_ok=True)

    logger.info(
        "Starting job hunt pipeline: role='%s' location='%s' industry='%s' batch=%s",
        args.role,
        args.location,
        args.industry,
        args.batch,
    )

    # Step 1: parse resume
    resume_text = parse_resume(args.resume)

    # Step 2: Scout — fetch listings and extract market signal
    listings = search_jobs(
        role=args.role,
        location=args.location,
        industry=args.industry,
        max_listings=args.max_listings,
    )
    if not listings:
        logger.error("No job listings found. Check SERPER_API_KEY and search terms.")
        sys.exit(1)

    listing_texts = [listing.as_text() for listing in listings]
    scout_report = run_scout(listing_texts)
    dump_json(scout_report, os.path.join(config.DATA_DIR, "scout_report.json"))

    # Steps 3-8: run the tailoring pipeline
    if args.batch:
        run_batch_mode(resume_text, listings, scout_report)
    else:
        run_single_mode(resume_text, listings, scout_report, args.role, args.industry)

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()
