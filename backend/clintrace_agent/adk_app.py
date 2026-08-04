"""Shared ADK App for local dev UI, runtime, and Agent Engine."""

from __future__ import annotations

from google.adk.apps import App

from clintrace_agent.agent import build_root_agent
from clintrace_agent.plugins import PatientInputPlugin


# Must match the agent package directory name for ADK web session lookup.
ADK_APP_NAME = "clintrace_agent"


def build_app() -> App:
    """Return the ClinTrace App with plugins required for ADK web."""
    return App(
        name=ADK_APP_NAME,
        root_agent=build_root_agent(),
        plugins=[PatientInputPlugin()],
    )


app = build_app()
