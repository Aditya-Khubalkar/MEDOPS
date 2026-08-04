"""AuditReporter sub-agent — audit document via ADK skill."""

from google.adk.agents import LlmAgent

from ..config import DEFAULT_MODEL, INLINE_SKILLS
from ..skills_loader import agent_instruction_with_skill, skill_toolset_for

_PREAMBLE = """You are the clinical documentation specialist for ClinTrace.

Follow the skill instructions below. Use ONLY the data below — do not ask for input.
Output the complete plain-text CLINTRACE TRIAGE AUDIT REPORT now.

Parsed symptoms:
{parsed_symptoms}

Severity score:
{severity_score}

Red flags:
{red_flags}

Routing:
{routing}

Phoenix feedback:
{feedback_analysis}"""

INSTRUCTION = (
    agent_instruction_with_skill("triage-audit-report", _PREAMBLE)
    if INLINE_SKILLS
    else """You are the clinical documentation specialist for ClinTrace.

Before producing output, call load_skill("triage-audit-report") and follow
its instructions exactly.

Use ONLY the data below. Do not ask for more input. Output the complete
plain-text CLINTRACE TRIAGE AUDIT REPORT now.

Parsed symptoms:
{parsed_symptoms}

Severity score:
{severity_score}

Red flags:
{red_flags}

Routing:
{routing}

Phoenix feedback:
{feedback_analysis}"""
)

audit_reporter = LlmAgent(
    name="audit_reporter",
    model=DEFAULT_MODEL,
    instruction=INSTRUCTION,
    tools=[] if INLINE_SKILLS else [skill_toolset_for("triage-audit-report")],
    output_key="audit_report",
    description="Generates human-readable audit report for the medical record.",
)
