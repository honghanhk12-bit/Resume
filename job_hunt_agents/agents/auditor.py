"""Agent 4: The Auditor.

Runs a final ATS compliance and quality check on the rewritten resume
before it is approved for submission.
"""

import logging

from schemas import AuditReport, RewrittenResume, ScoutReport
from utils.anthropic_client import call_agent_for_json

logger = logging.getLogger("job_hunt_agents")

SYSTEM_PROMPT = """You are an ATS compliance auditor. You receive a rewritten \
resume and the Scout Report from job market analysis. Your job is to run a \
final quality check before the resume is submitted.

Check and score the following (each out of 100, then give an overall score):
1. Keyword coverage: what % of the Scout Report's top_keywords appear in the resume?
2. XYZ compliance: what % of experience bullets follow the XYZ result-metric-method structure?
3. ATS readability: are there any tables, columns, text boxes, special characters, or non-standard section headers?
4. Quantification rate: what % of bullets contain a number, percentage, or measurable outcome?
5. Section completeness: are all standard ATS sections present (contact, summary, experience, education, skills)?

Return a structured AuditReport JSON with: overall_score, keyword_coverage_score, \
xyz_compliance_score, ats_readability_score, quantification_rate, \
section_completeness_score, issues_found (list), and approved (boolean - true \
if overall_score >= 80).

If approved is false, list exactly what the Surgeon must fix."""


def run_auditor(resume: RewrittenResume, scout_report: ScoutReport) -> AuditReport:
    """Run the Auditor agent against a rewritten resume.

    Args:
        resume: The RewrittenResume produced by the Surgeon agent.
        scout_report: The ScoutReport used to check keyword coverage.

    Returns:
        A validated AuditReport.
    """
    logger.info("[Auditor] Running ATS compliance audit...")

    user_message = (
        "REWRITTEN RESUME (JSON):\n"
        f"{resume.model_dump_json(indent=2)}\n\n"
        "SCOUT REPORT (JSON):\n"
        f"{scout_report.model_dump_json(indent=2)}\n\n"
        "Audit the rewritten resume and produce the AuditReport."
    )

    report = call_agent_for_json(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_message,
        response_model=AuditReport,
        tool_name="emit_audit_report",
        tool_description="Emit the structured AuditReport JSON.",
    )

    status = "APPROVED" if report.approved else "REJECTED"
    logger.info(
        "[Auditor] Overall score: %d/100 (%s). Keyword coverage: %d%%. Issues: %d.",
        report.overall_score,
        status,
        report.keyword_coverage_score,
        len(report.issues_found),
    )
    return report
