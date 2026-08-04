"""Audit report from session state — no LLM (replaces audit_reporter when merged)."""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.genai import types
from typing_extensions import override

from clintrace_agent.audit_report_builder import build_audit_report_from_state


class DeterministicAuditReporter(BaseAgent):
    """Build CLINTRACE TRIAGE AUDIT REPORT from pipeline state."""

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        report = build_audit_report_from_state(dict(ctx.session.state))
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=report)],
            ),
            actions=EventActions(state_delta={"audit_report": report}),
        )


deterministic_audit = DeterministicAuditReporter(
    name="deterministic_audit",
    description="Formats audit report from state without an LLM call.",
)
