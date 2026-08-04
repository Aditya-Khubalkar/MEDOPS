"""Deterministic agents that split merged LLM JSON into session state keys."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from typing_extensions import override

from clintrace_agent.json_utils import parse_json_blob


class ExpandClinicalAssessmentAgent(BaseAgent):
    """Maps clinical_assessment JSON to severity_score and red_flags."""

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        blob = parse_json_blob(ctx.session.state.get("clinical_assessment"))
        severity = blob.get("severity_score", blob)
        red_flags = blob.get("red_flags", {"flags_detected": False, "alerts": []})
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "severity_score": json.dumps(severity, indent=2),
                    "red_flags": json.dumps(red_flags, indent=2),
                },
            ),
        )


expand_clinical = ExpandClinicalAssessmentAgent(
    name="expand_clinical",
    description="Splits merged clinical_assessment into severity_score and red_flags.",
)
