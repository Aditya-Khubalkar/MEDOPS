"""SymptomParser sub-agent — structured intake via ADK skill."""

from google.adk.agents import LlmAgent

from ..config import DEFAULT_MODEL, INLINE_SKILLS
from ..skills_loader import agent_instruction_with_skill, skill_toolset_for

_PREAMBLE = """You are the clinical intake parser for ClinTrace.

Follow the skill instructions below. Output structured JSON only.

Patient intake text is in {patient_input}."""

INSTRUCTION = (
    agent_instruction_with_skill("clinical-intake-parser", _PREAMBLE)
    if INLINE_SKILLS
    else """You are the clinical intake parser for ClinTrace.

Before producing output, call load_skill("clinical-intake-parser") and follow
its instructions exactly.

Patient intake text is in {patient_input}."""
)

symptom_parser = LlmAgent(
    name="symptom_parser",
    model=DEFAULT_MODEL,
    instruction=INSTRUCTION,
    tools=[] if INLINE_SKILLS else [skill_toolset_for("clinical-intake-parser")],
    output_key="parsed_symptoms",
    description="Parses raw patient intake text into structured clinical data.",
)
