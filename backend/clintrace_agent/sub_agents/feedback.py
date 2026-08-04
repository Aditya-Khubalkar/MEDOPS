"""Deterministic feedback agent — Phoenix REST, no extra LLM call."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.genai import types
from typing_extensions import override

from clintrace_agent.config import USE_PHOENIX_MCP
from clintrace_agent.json_utils import parse_json_blob
from clintrace_agent.phoenix_mcp_probe import probe_phoenix_mcp_list_traces
from clintrace_agent.tools.phoenix_history import query_phoenix_feedback
from clintrace_agent.trace_context import extract_chief_complaint_from_text


def _current_confidence(severity_score: object) -> float:
    data = parse_json_blob(severity_score)
    try:
        return float(data.get("confidence", 0.75))
    except (TypeError, ValueError):
        return 0.75


def _current_esi(severity_score: object) -> int | None:
    data = parse_json_blob(severity_score)
    esi = data.get("esi_level")
    if esi is None:
        return None
    try:
        level = int(esi)
        return level if 1 <= level <= 5 else None
    except (TypeError, ValueError):
        return None


_FEEDBACK_KEY = "feedback_analysis"


class DeterministicFeedbackAgent(BaseAgent):
    """Applies Phoenix historical overrides without an LLM round-trip."""

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        parsed = state.get("parsed_symptoms", "")
        patient_input = str(state.get("patient_input", ""))
        if not parsed or parsed == "{}":
            chief = extract_chief_complaint_from_text(patient_input)
            if not chief and patient_input:
                chief = patient_input[:80]
            parsed = json.dumps(
                {
                    "chief_complaint": chief or "unknown",
                    "symptoms": [],
                }
            )
        severity = state.get("severity_score", "")
        confidence = _current_confidence(severity)
        current_esi = _current_esi(severity)

        if USE_PHOENIX_MCP:
            await probe_phoenix_mcp_list_traces(limit=5)

        result = query_phoenix_feedback(
            parsed_symptoms=str(parsed),
            current_confidence=confidence,
            current_esi=current_esi,
            patient_input=patient_input or None,
        )
        payload = json.dumps(result, indent=2)

        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=payload)],
            ),
            actions=EventActions(
                state_delta={_FEEDBACK_KEY: payload},
            ),
        )


feedback_agent = DeterministicFeedbackAgent(
    name="feedback_agent",
    description=(
        "Recalibrates confidence from Phoenix ground_truth_eval annotations."
    ),
)
