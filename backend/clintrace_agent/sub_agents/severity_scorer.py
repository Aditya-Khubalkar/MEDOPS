"""SeverityScorer sub-agent — ESI assignment via ADK skill."""

from google.adk.agents import LlmAgent

from ..config import DEFAULT_MODEL, INLINE_SKILLS
from ..skills_loader import agent_instruction_with_skill, skill_toolset_for
from ..tools.medical_knowledge import esi_criteria_tool

_PREAMBLE = """You are the ESI severity scorer for ClinTrace.

Follow the skill instructions below. Use lookup_esi_criteria when debating levels.

Structured patient data is in {parsed_symptoms}."""

INSTRUCTION = (
    agent_instruction_with_skill("esi-severity-scoring", _PREAMBLE)
    if INLINE_SKILLS
    else """You are the ESI severity scorer for ClinTrace.

Before producing output, call load_skill("esi-severity-scoring") and follow
its instructions exactly.

Structured patient data is in {parsed_symptoms}."""
)

severity_scorer = LlmAgent(
    name="severity_scorer",
    model=DEFAULT_MODEL,
    instruction=INSTRUCTION,
    tools=(
        [esi_criteria_tool]
        if INLINE_SKILLS
        else [skill_toolset_for("esi-severity-scoring"), esi_criteria_tool]
    ),
    output_key="severity_score",
    description="Assigns ESI 1-5 severity with confidence and reasoning.",
)
