"""Apply deterministic routing fallback after specialist_router."""

from __future__ import annotations

import json
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from typing_extensions import override

from clintrace_agent.routing_fallback import complete_routing_from_state


class EnforceRoutingAgent(BaseAgent):
    """Merge LLM routing with ESI/red-flag safety rules."""

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        routing = complete_routing_from_state(dict(ctx.session.state))
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"routing": json.dumps(routing, indent=2)},
            ),
        )


enforce_routing = EnforceRoutingAgent(
    name="enforce_routing",
    description="Ensures stroke/ESI pathways have valid routing in session state.",
)
