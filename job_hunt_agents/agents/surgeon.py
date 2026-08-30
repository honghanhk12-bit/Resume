"""Agent 3: The Surgeon.

Rewrites the resume's content using Google's XYZ bullet formula, embeds
Scout Report keywords naturally, and strips ATS-breaking formatting.
"""

import logging
from typing import List, Optional

from schemas import RewrittenResume, ScoutReport, StrategyReport
from utils.anthropic_client import call_agent_for_json

logger = logging.getLogger("job_hunt_agents")

SYSTEM_PROMPT = """You are a professional resume writer specialising in \
ATS-compliant, high-impact bullet points. You rewrite resume content using \
Google's XYZ formula: 'Accomplished [X], measured by [Y], by doing [Z].'

Your rules:
- Every bullet must follow XYZ or a close variant: result + metric or evidence + method
- Embed keywords from the provided keyword list naturally - never stuff them
- Never fabricate metrics. If no metric exists, use qualitative evidence (e.g. 'across 12 markets', 'for a portfolio of 480+ offices')
- Strip all ATS-breaking formatting: no tables, no text boxes, no columns, no graphics, no special characters except hyphens and pipes
- Keep bullets between 15 and 30 words
- Use past tense for previous roles, present tense for current role
- Return the complete rewritten resume as a structured JSON with sections preserved"""


def run_surgeon(
    resume_text: str,
    strategy_report: StrategyReport,
    scout_report: ScoutReport,
    fix_instructions: Optional[List[str]] = None,
) -> RewrittenResume:
    """Run the Surgeon agent to rewrite the resume.

    Args:
        resume_text: The candidate's original resume text.
        strategy_report: The StrategyReport from the Strategist agent.
        scout_report: The ScoutReport from the Scout agent.
        fix_instructions: Optional list of issues from a prior AuditReport
            to address on a retry pass.

    Returns:
        A validated RewrittenResume.
    """
    logger.info("[Surgeon] Rewriting resume bullets in XYZ format...")

    user_message = (
        "ORIGINAL RESUME:\n"
        f"{resume_text}\n\n"
        "STRATEGY REPORT (JSON):\n"
        f"{strategy_report.model_dump_json(indent=2)}\n\n"
        "SCOUT REPORT KEYWORDS (JSON):\n"
        f"{scout_report.model_dump_json(indent=2)}\n\n"
        "Rewrite the complete resume following the recommended section order, "
        "closing the identified gaps, and rewriting the flagged bullets into "
        "XYZ format with embedded keywords."
    )

    if fix_instructions:
        formatted_fixes = "\n".join(f"- {issue}" for issue in fix_instructions)
        user_message += (
            "\n\nIMPORTANT: A prior draft failed ATS audit. You MUST fix the "
            f"following issues in this rewrite:\n{formatted_fixes}"
        )
        logger.info(
            "[Surgeon] Retrying with %d fix instructions from Auditor.",
            len(fix_instructions),
        )

    resume = call_agent_for_json(
        system_prompt=SYSTEM_PROMPT,
        user_message=user_message,
        response_model=RewrittenResume,
        tool_name="emit_rewritten_resume",
        tool_description="Emit the complete RewrittenResume JSON.",
    )

    total_bullets = sum(len(entry.bullets) for entry in resume.experience)
    logger.info(
        "[Surgeon] Rewrote %d bullets across %d experience entries.",
        total_bullets,
        len(resume.experience),
    )
    return resume
