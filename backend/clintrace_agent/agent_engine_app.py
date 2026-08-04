"""Vertex AI Agent Engine entry point for ClinTrace."""

from __future__ import annotations

import logging
import os
from typing import Any

import vertexai
from dotenv import load_dotenv
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.cloud import logging as google_cloud_logging
from vertexai.agent_engines.templates.adk import AdkApp

from clintrace_agent.adk_app import app
from clintrace_agent.app_utils.telemetry import setup_telemetry
from clintrace_agent.app_utils.typing import Feedback

load_dotenv()

# Packaged clintrace_agent/.env must not override reserved Agent Engine variables.
if os.environ.get("GOOGLE_CLOUD_REGION"):
    os.environ.pop("GOOGLE_CLOUD_LOCATION", None)
    os.environ.pop("GOOGLE_CLOUD_PROJECT", None)

gemini_location = os.environ.get("CLINICTRACE_VERTEX_LOCATION")
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")


def _runtime_project_id() -> str | None:
    """Resolve project id without Cloud Resource Manager lookup.

    Agent Engine may set ``GOOGLE_CLOUD_PROJECT`` to the numeric project
    number. ``vertexai.init`` then calls the CRM API to convert it, which
    fails if that API is disabled or slow to propagate.
    """
    project = (
        os.environ.get("GOOGLE_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    if project and not str(project).isdigit():
        return project
    # Fallback when only the project number is injected at runtime.
    return os.environ.get("GOOGLE_PROJECT_ID")


def _agent_engine_location() -> str:
    """Region where this Reasoning Engine resource is deployed.

    Do not use ``CLINICTRACE_VERTEX_LOCATION`` here — that targets Gemini
    (often ``global``) and is unrelated to Agent Engine session APIs.
    """
    return (
        os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION")
        or os.environ.get("GOOGLE_CLOUD_REGION")
        or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    )


def _build_vertex_session_service():
    """Bind sessions to this Agent Engine resource (not in-memory/local)."""
    engine_id = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID", "").strip()
    if not engine_id:
        from google.adk.sessions.in_memory_session_service import (
            InMemorySessionService,
        )

        logging.warning(
            "GOOGLE_CLOUD_AGENT_ENGINE_ID unset; using InMemorySessionService"
        )
        return InMemorySessionService()

    from google.adk.sessions.vertex_ai_session_service import (
        VertexAiSessionService,
    )

    project = _runtime_project_id()
    location = _agent_engine_location()
    logging.info(
        "VertexAiSessionService project=%s location=%s engine_id=%s",
        project,
        location,
        engine_id,
    )
    return VertexAiSessionService(
        project=project,
        location=location,
        agent_engine_id=engine_id,
    )


def _configure_gemini_env() -> None:
    """Set GenAI/ADK env for Vertex publisher model calls.

    Agent Engine injects ``GOOGLE_CLOUD_REGION`` for the engine itself
    (``us-central1``). Gemini 3.5+ must use ``CLINICTRACE_VERTEX_LOCATION``
    (typically ``global``) and the string project id — not ADC's tenant
    project or the engine region.
    """
    gemini_region = os.environ.get("CLINICTRACE_VERTEX_LOCATION", "global")
    project = _runtime_project_id()
    if project:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project
        os.environ["GOOGLE_PROJECT_ID"] = project
    os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_region
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
    logging.info(
        "Gemini env project=%s location=%s",
        os.environ.get("GOOGLE_CLOUD_PROJECT"),
        gemini_region,
    )


class AgentEngineApp(AdkApp):
    """Agent Engine wrapper with logging and feedback registration."""

    def set_up(self) -> None:
        """Initialize the agent engine app with logging and telemetry."""
        import clintrace_agent.instrumentation  # noqa: F401 — Phoenix OTel export

        setup_telemetry()
        os.environ.setdefault(
            "GOOGLE_CLOUD_AGENT_ENGINE_LOCATION",
            _agent_engine_location(),
        )
        super().set_up()
        _configure_gemini_env()
        project = _runtime_project_id()
        gemini_region = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
        if project:
            vertexai.init(project=project, location=gemini_region)
        else:
            vertexai.init(location=gemini_region)
        logging.basicConfig(level=logging.INFO)
        try:
            gcl_client = google_cloud_logging.Client(project=_runtime_project_id())
            self._gcl_logger = gcl_client.logger(__name__)
        except Exception as exc:
            logging.warning("Cloud Logging unavailable, using stdlib: %s", exc)
            self._gcl_logger = None

    def register_feedback(self, feedback: dict[str, Any]) -> None:
        """Collect and log feedback."""
        feedback_obj = Feedback.model_validate(feedback)
        payload = feedback_obj.model_dump()
        if self._gcl_logger is not None:
            self._gcl_logger.log_struct(payload, severity="INFO")
        else:
            logging.getLogger(__name__).info("feedback: %s", payload)

    def register_operations(self) -> dict[str, list[str]]:
        """Register the operations of the Agent."""
        operations = super().register_operations()
        operations[""] = [*operations.get("", []), "register_feedback"]
        return operations


agent_engine = AgentEngineApp(
    app=app,
    enable_tracing=True,
    session_service_builder=_build_vertex_session_service,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=logs_bucket_name)
        if logs_bucket_name
        else InMemoryArtifactService()
    ),
)

# Backward compatibility for callers expecting adk_app.
adk_app = agent_engine
