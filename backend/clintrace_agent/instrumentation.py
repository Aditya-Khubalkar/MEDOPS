"""Phoenix tracing setup for ClinTrace.

Must be imported before any ADK agent code to ensure all spans are captured.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _configure_google_genai_env() -> None:
    """Map project env vars and pick Vertex (ADC) vs Gemini API (key)."""
    if not os.getenv("GOOGLE_CLOUD_PROJECT") and os.getenv("GOOGLE_PROJECT_ID"):
        os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ["GOOGLE_PROJECT_ID"]
    model = os.getenv("CLINICTRACE_MODEL") or os.getenv("GEMINI_MODEL", "")
    vertex_location = os.getenv("CLINICTRACE_VERTEX_LOCATION")
    if "3.5" in model and vertex_location in (None, "", "us-central1"):
        vertex_location = "global"
    if os.getenv("GOOGLE_CLOUD_REGION"):
        # Agent Engine injects GOOGLE_CLOUD_LOCATION for instance routing.
        # Only set CLINICTRACE_VERTEX_LOCATION for Gemini; do not override
        # the reserved platform variable.
        if vertex_location:
            os.environ["CLINICTRACE_VERTEX_LOCATION"] = vertex_location
        return
    if vertex_location:
        os.environ["CLINICTRACE_VERTEX_LOCATION"] = vertex_location
        os.environ["GOOGLE_CLOUD_LOCATION"] = vertex_location
    else:
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in (
        "true",
        "1",
    )
    if use_vertex:
        # Vertex aiplatform.googleapis.com rejects API keys; use ADC/OAuth.
        for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            os.environ.pop(key, None)


_configure_google_genai_env()

from phoenix.otel import register  # noqa: E402
from openinference.instrumentation.google_adk import (  # noqa: E402
    GoogleADKInstrumentor,
)

tracer_provider = register(
    project_name=os.getenv("PHOENIX_PROJECT_NAME", "clinictrace"),
    auto_instrument=True,
)

GoogleADKInstrumentor().instrument(tracer_provider=tracer_provider)

try:
    from openinference.instrumentation.mcp import MCPInstrumentor  # noqa: E402

    MCPInstrumentor().instrument(tracer_provider=tracer_provider)
except ImportError:  # pragma: no cover - optional dependency
    pass
