"""RedFlagDetector sub-agent — time-critical screening via ADK skill."""

from google.adk.agents import LlmAgent

from ..config import DEFAULT_MODEL, INLINE_SKILLS
from ..skills_loader import agent_instruction_with_skill, skill_toolset_for
from ..tools.medical_knowledge import red_flag_criteria_tool

_PREAMBLE = """You are the red-flag screening specialist for ClinTrace.

Follow the skill instructions below. Use lookup_red_flag_criteria for thresholds.

Structured patient data is in {parsed_symptoms}."""

INSTRUCTION = (
    agent_instruction_with_skill("red-flag-screening", _PREAMBLE)
    if INLINE_SKILLS
    else """You are the red-flag screening specialist for ClinTrace.

Before producing output, call load_skill("red-flag-screening") and follow
its instructions exactly.

Structured patient data is in {parsed_symptoms}."""
)

red_flag_detector = LlmAgent(
    name="red_flag_detector",
    model=DEFAULT_MODEL,
    instruction=INSTRUCTION,
    tools=(
        [red_flag_criteria_tool]
        if INLINE_SKILLS
        else [skill_toolset_for("red-flag-screening"), red_flag_criteria_tool]
    ),
    output_key="red_flags",
    description=(
        "Screens for sepsis, stroke, STEMI, and other time-critical conditions."
    ),
)
