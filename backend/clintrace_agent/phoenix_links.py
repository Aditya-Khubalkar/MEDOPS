"""Build Phoenix Cloud deep links.

Phoenix documents shareable URLs via /redirects/... using human-readable
identifiers (project name, OpenTelemetry trace ID). Direct /projects/{id}/traces/...
links require Global IDs and can trigger Relay "Invariant failed" errors.
See: https://arize.com/docs/phoenix/tracing/how-to-tracing/advanced/constructing-urls
"""

from __future__ import annotations

import os
from urllib.parse import quote


def _normalize_otel_trace_id(trace_id: str) -> str:
    return trace_id.strip().lower().replace("-", "")


def build_phoenix_trace_url(otel_trace_id: str) -> str:
    """Return a Phoenix Cloud URL for this triage run's trace.

    Uses the OTEL trace ID from the ClinTrace pipeline (32 hex chars).
    Phoenix resolves it via getTraceByOtelId on /redirects/traces/{trace_id}.
    """
    base = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "").rstrip("/")
    if not base or not otel_trace_id:
        return "#"

    tid = quote(_normalize_otel_trace_id(otel_trace_id), safe="")
    return f"{base}/redirects/traces/{tid}"


def build_phoenix_project_url() -> str:
    """Link to the ClinTrace project by name (PHOENIX_PROJECT_NAME)."""
    base = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "").rstrip("/")
    if not base:
        return "#"
    name = quote(
        os.getenv("PHOENIX_PROJECT_NAME", "clinictrace"),
        safe="",
    )
    return f"{base}/redirects/projects/{name}"
