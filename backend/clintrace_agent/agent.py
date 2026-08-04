"""ClinTrace root agent definition.

Orchestrates the clinical triage pipeline as an ADK 2.0 Workflow graph,
with a feedback step tied to Phoenix (REST for speed; optional MCP enrichment).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from google.adk import Workflow
from google.adk.workflow import JoinNode
from google.adk.agents import LlmAgent

from .config import (
    DEFAULT_MODEL,
    INLINE_SKILLS,
    MERGE_TRIAGE_LLM_STEPS,
    USE_LLM_FEEDBACK,
)
from .phoenix_mcp_connection import build_phoenix_mcp_toolset
from .sub_agents import (
    audit_reporter,
    specialist_router,
    symptom_parser,
)
from .sub_agents.clinical_assessor import clinical_assessor
from .sub_agents.deterministic_audit import deterministic_audit
from .sub_agents.feedback import feedback_agent as deterministic_feedback
from .sub_agents.red_flag_detector import red_flag_detector
from .sub_agents.severity_scorer import severity_scorer
from .sub_agents.enforce_routing import enforce_routing
from .sub_agents.state_expanders import expand_clinical
from .skills_loader import agent_instruction_with_skills, skill_toolset_for
from .tools.feedback_query import confidence_adjustment_tool, trace_query_tool
from .tools.phoenix_history import phoenix_feedback_tool

_FEEDBACK_PREAMBLE = """You are the ClinTrace feedback analyst.

Session state includes parsed_symptoms, severity_score, red_flags, routing.
Minimize latency; output ONLY the final feedback JSON."""

_FEEDBACK_INSTRUCTION = (
    agent_instruction_with_skills(
        ["phoenix-feedback-loop", "phoenix-similarity-matching"],
        _FEEDBACK_PREAMBLE,
    )
    if INLINE_SKILLS
    else """You are the ClinTrace feedback analyst.

Before acting, call load_skill("phoenix-feedback-loop") and
load_skill("phoenix-similarity-matching"), then follow them exactly.

Session state includes parsed_symptoms, severity_score, red_flags, routing.
Minimize latency; output ONLY the final feedback JSON."""
)


def _feedback_tools() -> list[Any]:
    """Build feedback tools; MCP toolset is created here, not at module import."""
    tools: list[Any] = [
        phoenix_feedback_tool,
        trace_query_tool,
        confidence_adjustment_tool,
    ]
    phoenix_mcp = build_phoenix_mcp_toolset()
    if phoenix_mcp is not None:
        tools.insert(0, phoenix_mcp)
    return tools


def build_root_agent() -> Workflow:
    """Build the ClinTrace triage workflow graph."""
    feedback_tools = _feedback_tools()
    llm_feedback_agent = LlmAgent(
        name="feedback_agent",
        model=DEFAULT_MODEL,
        instruction=_FEEDBACK_INSTRUCTION,
        tools=(
            feedback_tools
            if INLINE_SKILLS
            else [
                skill_toolset_for(
                    "phoenix-feedback-loop",
                    additional_tools=feedback_tools,
                ),
            ]
        ),
        output_key="feedback_analysis",
        description="Phoenix MCP + REST feedback for confidence recalibration.",
    )

    feedback_step = (
        llm_feedback_agent if USE_LLM_FEEDBACK else deterministic_feedback
    )

    if MERGE_TRIAGE_LLM_STEPS:
        audit_step = deterministic_audit
        return Workflow(
            name="triage_pipeline",
            description=(
                "Clinical triage (merged): parse → assess → route → "
                "Phoenix feedback → deterministic audit."
            ),
            edges=[
                (
                    "START",
                    symptom_parser,
                    clinical_assessor,
                    expand_clinical,
                    specialist_router,
                    enforce_routing,
                    feedback_step,
                    audit_step,
                ),
            ],
        )

    clinical_join = JoinNode(
        name="clinical_join",
        description="Synchronizes parallel severity and red-flag analysis.",
    )
    return Workflow(
        name="triage_pipeline",
        description=(
            "Clinical triage: parse -> parallel score/flags -> route -> "
            "Phoenix feedback -> audit report."
        ),
        edges=[
            (
                "START",
                symptom_parser,
                (severity_scorer, red_flag_detector),
                clinical_join,
                specialist_router,
                enforce_routing,
                feedback_step,
                audit_reporter,
            ),
        ],
    )


@lru_cache(maxsize=1)
def get_root_agent() -> Workflow:
    """Return the singleton root workflow (built on first use)."""
    return build_root_agent()


def __getattr__(name: str) -> Workflow:
    """Lazy ``root_agent`` for importers that expect a module attribute."""
    if name == "root_agent":
        return get_root_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
