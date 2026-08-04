"""Combined ESI scoring + red-flag screening (one LLM call)."""

from google.adk.agents import LlmAgent

from clintrace_agent.config import DEFAULT_MODEL, INLINE_SKILLS
from clintrace_agent.skills_loader import (
    agent_instruction_with_skills,
    load_clinictrace_skill,
)
from google.adk.tools.skill_toolset import SkillToolset
from clintrace_agent.tools.medical_knowledge import esi_criteria_tool, red_flag_criteria_tool

_PREAMBLE = """You are the clinical assessment specialist for ClinTrace.

In ONE response, assign ESI severity AND screen red flags from structured intake.

Structured patient data is in {parsed_symptoms}.

Output ONLY a JSON object (no markdown fences) with exactly two keys:
- "severity_score": same schema as ESI scoring (esi_level, confidence, reasoning, ...)
- "red_flags": same schema as red-flag screening (flags_detected, alerts, status, ...)

Use lookup_esi_criteria and lookup_red_flag_criteria when thresholds are unclear."""

INSTRUCTION = (
    agent_instruction_with_skills(
        ["esi-severity-scoring", "red-flag-screening"],
        _PREAMBLE,
    )
    if INLINE_SKILLS
    else """You are the clinical assessment specialist for ClinTrace.

Call load_skill("esi-severity-scoring") and load_skill("red-flag-screening"),
then produce ONE JSON object with keys severity_score and red_flags only.

Structured patient data is in {parsed_symptoms}."""
)

_tools = [esi_criteria_tool, red_flag_criteria_tool]

clinical_assessor = LlmAgent(
    name="clinical_assessor",
    model=DEFAULT_MODEL,
    instruction=INSTRUCTION,
    tools=(
        _tools
        if INLINE_SKILLS
        else [
            SkillToolset(
                skills=[
                    load_clinictrace_skill("esi-severity-scoring"),
                    load_clinictrace_skill("red-flag-screening"),
                ],
                additional_tools=_tools,
            ),
        ]
    ),
    output_key="clinical_assessment",
    description=(
        "Assigns ESI and screens red flags in a single model call."
    ),
)
