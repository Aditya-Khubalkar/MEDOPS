"""SpecialistRouter sub-agent — ED routing via ADK skill."""

from google.adk.agents import LlmAgent

from clintrace_agent.config import DEFAULT_MODEL, INLINE_SKILLS
from clintrace_agent.skills_loader import agent_instruction_with_skill, skill_toolset_for

_PREAMBLE = """You are the ED routing specialist for ClinTrace.

Follow the skill instructions below. Output ONLY the routing JSON object.

CRITICAL: Never leave primary_destination, priority, or rationale as N/A or empty
when ESI is 1-2 or red_flags_detected is non-empty. Stroke → STROKE_TEAM +
Neurology; STEMI/ACS → CARDIAC_CATH + Cardiology; ESI-2 without specific pathway
→ ED_ACUTE with immediate priority.

Parsed symptoms:
{parsed_symptoms}

Severity score:
{severity_score}

Red flags:
{red_flags}"""

INSTRUCTION = (
    agent_instruction_with_skill("ed-specialist-routing", _PREAMBLE)
    if INLINE_SKILLS
    else """You are the ED routing specialist for ClinTrace.

Before producing output, call load_skill("ed-specialist-routing") and follow
its instructions exactly.

Parsed symptoms:
{parsed_symptoms}

Severity score:
{severity_score}

Red flags:
{red_flags}

Output ONLY the routing JSON object."""
)

specialist_router = LlmAgent(
    name="specialist_router",
    model=DEFAULT_MODEL,
    instruction=INSTRUCTION,
    tools=[] if INLINE_SKILLS else [skill_toolset_for("ed-specialist-routing")],
    output_key="routing",
    description="Routes patient to appropriate department and specialist.",
)
