"""Unified triage runtime — local InMemoryRunner or remote Agent Engine.

Set AGENT_ENGINE_RESOURCE_ID to call a deployed Vertex AI Agent Engine.
Otherwise runs the pipeline in-process (local dev and Cloud Run all-in-one).
"""

import json
import os

from google.genai import types
from opentelemetry import trace
from phoenix.otel import using_session

from clintrace_agent.action_composer import build_triage_actions
from clintrace_agent.audit_report_builder import (
    build_audit_report_from_state,
    is_valid_audit_report,
)
from clintrace_agent.models import TriageResult
from clintrace_agent.phoenix_trace_lookup import otel_trace_id_from_span_context, resolve_trace_id
from clintrace_agent.trace_context import (
    stamp_triage_root_span_end,
    stamp_triage_root_span_start,
)

_tracer = trace.get_tracer("clinictrace.pipeline")


def _text_from_event(event) -> str:
    """Extract plain text from an ADK event, if present."""
    if not event.content or not event.content.parts:
        return ""
    parts = [p.text for p in event.content.parts if p.text]
    return "\n".join(parts)


async def run_triage(patient_input: str) -> TriageResult:
    """Run triage locally or against a remote Agent Engine.

    Args:
        patient_input: Free-text nursing intake notes.

    Returns:
        TriageResult with audit report, structured actions, and trace ID.
    """
    engine_resource = os.getenv("AGENT_ENGINE_RESOURCE_ID", "").strip()
    if engine_resource:
        return await _run_triage_agent_engine(patient_input, engine_resource)
    return await _run_triage_local(patient_input)


async def _run_triage_local(patient_input: str) -> TriageResult:
    """Run triage with the in-process ADK runner."""
    from google.adk.runners import InMemoryRunner

    from clintrace_agent.adk_app import app

    with _tracer.start_as_current_span("clinictrace.triage") as span:
        runner = InMemoryRunner(app=app)
        session = await runner.session_service.create_session(
            app_name=app.name,
            user_id="nurse_intake",
            state={"patient_input": patient_input},
        )

        stamp_triage_root_span_start(
            span,
            patient_input=patient_input,
            session_id=session.id,
        )

        final_response = ""
        with using_session(session.id):
            async for event in runner.run_async(
                user_id="nurse_intake",
                session_id=session.id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=patient_input)],
                ),
            ):
                text = _text_from_event(event)
                if not text:
                    continue
                if event.author in (
                    "audit_reporter",
                    "deterministic_audit",
                ) and is_valid_audit_report(text):
                    final_response = text
                elif "CLINTRACE TRIAGE AUDIT REPORT" in text.upper():
                    final_response = text
                elif event.is_final_response() and is_valid_audit_report(text):
                    final_response = text

        updated = await runner.session_service.get_session(
            app_name=app.name,
            user_id="nurse_intake",
            session_id=session.id,
        )
        actions: dict = {}
        detail_audit_report: str | None = None
        if updated:
            state_report = updated.state.get("audit_report", "")
            if isinstance(state_report, str) and is_valid_audit_report(
                state_report
            ):
                final_response = state_report
            elif state_report is not None and is_valid_audit_report(
                str(state_report)
            ):
                final_response = str(state_report)

            if not is_valid_audit_report(final_response):
                final_response = build_audit_report_from_state(updated.state)

            feedback_raw = updated.state.get("feedback_analysis", "")
            if isinstance(feedback_raw, str):
                try:
                    feedback_data = json.loads(feedback_raw)
                except json.JSONDecodeError:
                    feedback_data = {}
            elif isinstance(feedback_raw, dict):
                feedback_data = feedback_raw
            else:
                feedback_data = {}
            if feedback_data.get("esi_calibration_applied"):
                if is_valid_audit_report(final_response):
                    detail_audit_report = final_response
                final_response = build_audit_report_from_state(updated.state)

            actions = build_triage_actions(
                updated.state,
                audit_report=final_response,
            )
            stamp_triage_root_span_end(
                span,
                audit_report=final_response,
                parsed_symptoms=updated.state.get("parsed_symptoms"),
                severity_score=updated.state.get("severity_score"),
            )

        otel_id = otel_trace_id_from_span_context()
        if not otel_id and span.get_span_context().is_valid:
            otel_id = format(span.get_span_context().trace_id, "032x")

        trace_id = resolve_trace_id(
            preferred_otel=otel_id,
            session_id=session.id,
        )

    return TriageResult(
        audit_report=final_response,
        trace_id=trace_id,
        actions=actions,
        detail_audit_report=detail_audit_report,
        session_id=session.id,
    )


async def _run_triage_agent_engine(
    patient_input: str,
    resource_name: str,
) -> TriageResult:
    """Run triage against a deployed Vertex AI Agent Engine."""
    from datetime import datetime, timezone

    import vertexai
    from vertexai import agent_engines

    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv(
        "GOOGLE_PROJECT_ID"
    )
    # Agent Engine is deployed in us-central1; Gemini inference uses global.
    location = os.getenv("AGENT_ENGINE_REGION", "us-central1")

    if os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("true", "1"):
        vertexai.init(project=project, location=location)
    else:
        vertexai.init(
            project=project,
            location=location,
            api_key=os.getenv("GOOGLE_API_KEY"),
        )

    from clintrace_agent.action_composer import build_triage_actions

    remote_agent = agent_engines.get(resource_name)
    session = remote_agent.create_session(user_id="clinictrace_ui")
    session_id = session["id"]
    run_started_at = datetime.now(timezone.utc)

    final_response = ""
    with _tracer.start_as_current_span("clinictrace.triage") as span:
        stamp_triage_root_span_start(
            span,
            patient_input=patient_input,
            session_id=session_id,
        )
        with using_session(session_id):
            for event in remote_agent.stream_query(
                user_id="clinictrace_ui",
                session_id=session_id,
                message=patient_input,
            ):
                if isinstance(event, dict):
                    content = event.get("content", {})
                    parts = content.get("parts", [])
                    for part in parts:
                        if isinstance(part, dict) and part.get("text"):
                            final_response = part["text"]
                        elif hasattr(part, "text"):
                            final_response = part.text

        stamp_triage_root_span_end(span, audit_report=final_response)

        ui_trace_id = otel_trace_id_from_span_context()
        agent_trace_id = resolve_trace_id(
            session_id=session_id,
            prefer_session=True,
            session_retries=5,
            run_started_at=run_started_at,
        )
        trace_id = ui_trace_id or agent_trace_id or ""
        if (
            ui_trace_id
            and agent_trace_id
            and ui_trace_id != agent_trace_id
            and span.is_recording()
        ):
            span.set_attribute("clintrace.agent_trace_id", agent_trace_id)

    actions = build_triage_actions({}, audit_report=final_response)

    return TriageResult(
        audit_report=final_response,
        trace_id=trace_id,
        actions=actions,
        session_id=session_id,
        run_started_at=run_started_at.isoformat(),
    )
