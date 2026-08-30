"""Agent 1: The Scout.

Analyses a batch of job listing texts and extracts the ATS/recruiter
signal that matters: recurring keywords, required/preferred skills,
repeated phrasing, seniority signals, and ATS red flags.
"""

import logging
from typing import List

from schemas import ScoutReport
from utils.anthropic_client import call_agent_for_json

logger = logging.getLogger("job_hunt_agents")

# Cap per-listing length so a batch of ~100 listings stays within a
# reasonable context budget (most Serper job descriptions are truncated
# anyway, but some job boards return very long raw text).
MAX_CHARS_PER_LISTING = 2000

SYSTEM_PROMPT = """You are a job market intelligence analyst. Your job is to \
analyse a batch of job listings for a target role and extract the signal that \
matters for ATS and recruiter ranking.

Given a list of job listing texts, return a structured JSON object containing:
- top_keywords: the 30 most frequently appearing technical and functional keywords, ranked by frequency
- required_skills: skills listed as required or essential across 50%+ of listings
- preferred_skills: skills listed as preferred, desired, or nice-to-have
- repeated_phrases: exact phrases that appear verbatim across multiple listings
- seniority_signals: words and phrases that indicate the seniority level of the role
- ats_red_flags: formatting or structural patterns suggesting strict ATS parsing

Return only valid JSON. No commentary."""


def run_scout(job_listing_texts: List[str]) -> ScoutReport:
    """Run the Scout agent over a batch of job listing texts.

    Args:
        job_listing_texts: Raw text of each job listing.

    Returns:
        A validated ScoutReport.
    """
    logger.info("[Scout] Analysing %d job listings...", len(job_listing_texts))

    truncated_texts = [text[:MAX_CHARS_PER_LISTING] for text in job_listing_texts]
    joined_listings = "\n\n---LISTING---\n\n".join(truncated_texts)
    user_message = (
        f"Here are {len(job_listing_texts)} job listings for the target role. "
        f"Analyse them and extract the ScoutReport.\n\n{joined_listings}"
    )

    report = call_agent_for_json(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_message,
        response_model=ScoutReport,
        tool_name="emit_scout_report",
        tool_description="Emit the structured ScoutReport JSON.",
    )

    logger.info(
        "[Scout] Found %d top keywords, %d required skills, %d preferred skills.",
        len(report.top_keywords),
        len(report.required_skills),
        len(report.preferred_skills),
    )
    return report
