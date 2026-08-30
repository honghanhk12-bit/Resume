"""Agent 2: The Strategist.

Scores the candidate's resume against the Scout Report, identifies gaps
and strengths, and recommends a section order and bullets to rewrite.
"""

import logging

from schemas import ScoutReport, StrategyReport
from utils.anthropic_client import call_agent_for_json

logger = logging.getLogger("job_hunt_agents")

SYSTEM_PROMPT = """You are a resume strategy consultant specialising in ATS \
optimisation. You will receive a candidate's current resume and a Scout \
Report containing the keywords, skills, and phrases that appear most \
frequently in real job listings for their target role.

Your job is to:
1. Score the resume against the Scout Report (0-100 ATS match score) with clear reasoning
2. Identify gaps: skills or keywords in the report that are absent or weak in the resume
3. Identify strengths: resume content that maps well to the target role
4. Recommend a section order that puts the strongest ATS-relevant content in the top third of the document
5. Flag any existing bullet points that are vague, metric-free, or unlikely to pass ATS parsing

Return a structured JSON StrategyReport with fields: ats_score, gaps, strengths, \
recommended_section_order, bullets_to_rewrite, strategic_notes."""


def run_strategist(resume_text: str, scout_report: ScoutReport) -> StrategyReport:
    """Run the Strategist agent.

    Args:
        resume_text: The candidate's current resume as plain text.
        scout_report: The ScoutReport produced by the Scout agent.

    Returns:
        A validated StrategyReport.
    """
    logger.info("[Strategist] Scoring resume against Scout Report...")

    user_message = (
        "CANDIDATE RESUME:\n"
        f"{resume_text}\n\n"
        "SCOUT REPORT (JSON):\n"
        f"{scout_report.model_dump_json(indent=2)}\n\n"
        "Analyse the resume against the Scout Report and produce the StrategyReport."
    )

    report = call_agent_for_json(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_message,
        response_model=StrategyReport,
        tool_name="emit_strategy_report",
        tool_description="Emit the structured StrategyReport JSON.",
    )

    logger.info(
        "[Strategist] ATS score: %d/100. Gaps found: %d. Strengths found: %d.",
        report.ats_score,
        len(report.gaps),
        len(report.strengths),
    )
    return report
