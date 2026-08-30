"""Pydantic schemas shared by all four agents.

These double as the JSON-schema source for Anthropic tool-use definitions
(see utils/anthropic_client.py), guaranteeing every agent's output is
structured and validated.
"""

from typing import List

from pydantic import BaseModel, Field


# --- Agent 1: Scout ----------------------------------------------------------


class ScoutReport(BaseModel):
    top_keywords: List[str] = Field(
        description="The 30 most frequently appearing technical and functional "
        "keywords across the listings, ranked by frequency, most frequent first."
    )
    required_skills: List[str] = Field(
        description="Skills listed as required or essential across 50%+ of listings."
    )
    preferred_skills: List[str] = Field(
        description="Skills listed as preferred, desired, or nice-to-have."
    )
    repeated_phrases: List[str] = Field(
        description="Exact phrases that appear verbatim across multiple listings."
    )
    seniority_signals: List[str] = Field(
        description="Words and phrases that indicate the seniority level of the role."
    )
    ats_red_flags: List[str] = Field(
        description="Formatting or structural patterns suggesting strict ATS parsing."
    )


# --- Agent 2: Strategist ------------------------------------------------------


class StrategyReport(BaseModel):
    ats_score: int = Field(ge=0, le=100, description="ATS match score, 0-100.")
    score_reasoning: str = Field(description="Clear reasoning behind the ats_score.")
    gaps: List[str] = Field(
        description="Skills or keywords in the Scout Report absent or weak in the resume."
    )
    strengths: List[str] = Field(
        description="Resume content that maps well to the target role."
    )
    recommended_section_order: List[str] = Field(
        description="Section names in the order they should appear, strongest "
        "ATS-relevant content first."
    )
    bullets_to_rewrite: List[str] = Field(
        description="Existing bullet points that are vague, metric-free, or "
        "unlikely to pass ATS parsing."
    )
    strategic_notes: str = Field(description="Any additional strategic notes.")


# --- Agent 3: Surgeon ---------------------------------------------------------


class ExperienceEntry(BaseModel):
    title: str
    company: str
    dates: str
    bullets: List[str] = Field(description="Rewritten XYZ-format bullet points.")


class RewrittenResume(BaseModel):
    contact: str = Field(description="Name and contact details, single block of text.")
    summary: str = Field(description="Rewritten professional summary.")
    experience: List[ExperienceEntry]
    education: List[str] = Field(description="Education entries as formatted lines.")
    skills: List[str] = Field(description="Flat list of skills for the skills section.")


# --- Agent 4: Auditor ----------------------------------------------------------


class AuditReport(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    keyword_coverage_score: int = Field(ge=0, le=100)
    xyz_compliance_score: int = Field(ge=0, le=100)
    ats_readability_score: int = Field(ge=0, le=100)
    quantification_rate: int = Field(ge=0, le=100)
    section_completeness_score: int = Field(ge=0, le=100)
    issues_found: List[str]
    approved: bool = Field(
        description="True if overall_score >= 80, false otherwise."
    )
