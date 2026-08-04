"""Seed ``patient_input`` session state from chat user messages."""

from __future__ import annotations

from typing import Optional

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

PATIENT_INPUT_KEY = "patient_input"


def text_from_content(content: types.Content | None) -> str:
    """Extract plain text from a GenAI Content message."""
    if content is None or not content.parts:
        return ""
    parts = [part.text for part in content.parts if part.text]
    return "\n".join(parts).strip()


class PatientInputPlugin(BasePlugin):
    """Copy the latest user message into session state as ``patient_input``.

    ClinTrace agents reference ``{patient_input}`` in instructions and read
    ``patient_input`` from session state. ADK web sends intake as chat messages
    without pre-seeding state; this plugin bridges that gap. Callers that
    already set state (``runtime.py``, CLI) are unaffected — the same text is
    written again.
    """

    def __init__(self) -> None:
        super().__init__(name="patient_input")

    async def on_user_message_callback(
        self,
        *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> Optional[types.Content]:
        """Store user message text in session state before the run starts."""
        text = text_from_content(user_message)
        if text:
            invocation_context.session.state[PATIENT_INPUT_KEY] = text
        return None
