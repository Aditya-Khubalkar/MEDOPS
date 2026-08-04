"""Resolve Phoenix / OTel trace IDs (local runner and Agent Engine)."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import PHOENIX_PROJECT
from .trace_context import ROOT_SPAN_NAME, format_otel_trace_id

FEEDBACK_SPAN_NAME = "phoenix.query_feedback"


def _phoenix_client():
    from phoenix.client import Client

    base_url = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("PHOENIX_API_KEY", "")
    if not base_url or not api_key:
        return None
    return Client(base_url=base_url, api_key=api_key)


def lookup_otel_trace_id_by_session(
    session_id: str,
    *,
    limit: int = 5,
    retries: int = 1,
    retry_delay_s: float = 1.0,
) -> str | None:
    """Find the most recent OTel trace id for an ADK/Agent Engine session id.

    Phoenix stores ``session.id`` on spans when ``using_session`` is active.
    Agent Engine sessions map to the same identifier via ``get_traces`` filter.

    Args:
        session_id: ADK session id from InMemoryRunner or Agent Engine.
        limit: Max traces to inspect per attempt.
        retries: Number of attempts (Agent Engine traces may index slowly).
        retry_delay_s: Seconds between attempts.

    Returns:
        32-char OTel trace id hex string, or None if not found.
    """
    if not session_id:
        return None
    for attempt in range(max(1, retries)):
        found = _lookup_otel_trace_id_by_session_once(session_id, limit=limit)
        if found:
            return found
        if attempt < retries - 1:
            time.sleep(retry_delay_s)
    return None


def _lookup_otel_trace_id_by_session_once(
    session_id: str,
    *,
    limit: int = 5,
) -> str | None:
    client = _phoenix_client()
    if client is None:
        return None

    try:
        traces = client.traces.get_traces(
            project_identifier=PHOENIX_PROJECT,
            session_id=session_id,
            limit=limit,
            order="desc",
        )
    except Exception:  # noqa: BLE001
        return None

    for trace in traces:
        tid = _extract_otel_trace_id(trace)
        if tid:
            return tid
    return None


def _parse_span_start_time(span: dict[str, Any]) -> datetime | None:
    """Parse Phoenix span start_time to UTC datetime."""
    raw = span.get("start_time")
    if not raw:
        return None
    text = str(raw).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_otel_trace_id(trace_id: Any) -> str | None:
    if trace_id is None:
        return None
    text = str(trace_id).strip().lower().replace("-", "")
    if len(text) == 32 and all(c in "0123456789abcdef" for c in text):
        return text
    return None


def _trace_id_from_span(span: dict[str, Any]) -> str | None:
    ctx = span.get("context") or {}
    return _normalize_otel_trace_id(ctx.get("trace_id"))


def lookup_otel_trace_id_from_feedback_span(
    *,
    since: datetime | None = None,
    retries: int = 10,
    retry_delay_s: float = 2.0,
    limit: int = 8,
) -> str | None:
    """Resolve Agent Engine triage trace via ``phoenix.query_feedback`` span.

    Remote Agent Engine runs do not stamp ``session.id`` on exported spans, so
    session-based lookup often fails. The feedback tool span is always emitted
    on the agent triage trace and is the reliable anchor for deep links.
    """
    client = _phoenix_client()
    if client is None:
        return None

    since_utc = since.astimezone(timezone.utc) if since else None
    # Allow small clock skew between Cloud Run and Phoenix indexing.
    since_floor = since_utc - timedelta(seconds=45) if since_utc else None
    for attempt in range(max(1, retries)):
        try:
            spans = client.spans.get_spans(
                project_identifier=PHOENIX_PROJECT,
                name=FEEDBACK_SPAN_NAME,
                limit=limit,
            )
        except Exception:  # noqa: BLE001
            spans = []
        for span in spans:
            if not isinstance(span, dict):
                continue
            started = _parse_span_start_time(span)
            if since_floor and started and started < since_floor:
                continue
            tid = _trace_id_from_span(span)
            if tid:
                return tid
        if attempt < retries - 1:
            time.sleep(retry_delay_s)
    return None


def lookup_recent_triage_trace_id(
    *,
    limit: int = 5,
    retries: int = 8,
    retry_delay_s: float = 2.0,
) -> str | None:
    """Return the newest triage trace id from Phoenix.

    Prefer ``get_traces`` (recent ADK/Agent Engine runs). Fall back to named
    root spans for older local InMemoryRunner sessions.
    """
    client = _phoenix_client()
    if client is None:
        return None
    for attempt in range(max(1, retries)):
        try:
            traces = client.traces.get_traces(
                project_identifier=PHOENIX_PROJECT,
                limit=limit,
                order="desc",
            )
        except Exception:  # noqa: BLE001
            traces = []
        for trace in traces:
            tid = _extract_otel_trace_id(trace)
            if tid:
                return tid
        try:
            spans = client.spans.get_spans(
                project_identifier=PHOENIX_PROJECT,
                name=ROOT_SPAN_NAME,
                limit=limit,
            )
        except Exception:  # noqa: BLE001
            spans = []
        for span in spans:
            ctx = span.get("context") or {}
            tid = ctx.get("trace_id")
            if tid is None:
                continue
            text = str(tid).strip().lower().replace("-", "")
            if len(text) == 32 and all(c in "0123456789abcdef" for c in text):
                return text
        if attempt < retries - 1:
            time.sleep(retry_delay_s)
    return None


def _extract_otel_trace_id(trace: Any) -> str | None:
    """Pull OTel trace id from Phoenix TraceData (dict or model)."""
    if isinstance(trace, dict):
        ctx = trace.get("context") or {}
        tid = ctx.get("trace_id") or trace.get("trace_id") or trace.get("id")
    else:
        ctx = getattr(trace, "context", None) or {}
        tid = getattr(ctx, "trace_id", None) if ctx else None
        if not tid:
            tid = getattr(trace, "trace_id", None) or getattr(trace, "id", None)
    if tid is None:
        return None
    text = str(tid).strip().lower().replace("-", "")
    if len(text) == 32 and all(c in "0123456789abcdef" for c in text):
        return text
    return None


def resolve_trace_id(
    *,
    preferred_otel: str | None = None,
    session_id: str | None = None,
    prefer_session: bool = False,
    session_retries: int = 1,
    run_started_at: datetime | None = None,
) -> str:
    """Pick the best trace id for Phoenix deep links.

    Priority: session lookup (when ``prefer_session``) → explicit OTel id
    → session lookup → feedback-span lookup (Agent Engine) → empty string.
    """
    if prefer_session and session_id:
        looked_up = lookup_otel_trace_id_by_session(
            session_id,
            retries=session_retries,
        )
        if looked_up:
            return looked_up

    if preferred_otel:
        normalized = preferred_otel.strip().lower().replace("-", "")
        if len(normalized) == 32:
            return normalized

    if session_id:
        looked_up = lookup_otel_trace_id_by_session(
            session_id,
            retries=session_retries,
        )
        if looked_up:
            return looked_up

    if prefer_session or run_started_at is not None:
        feedback_tid = lookup_otel_trace_id_from_feedback_span(
            since=run_started_at,
            retries=session_retries,
        )
        if feedback_tid:
            return feedback_tid

    return ""


def otel_trace_id_from_span_context() -> str | None:
    """Read OTel trace id from the current recording span."""
    from opentelemetry import trace as otel_trace

    span = otel_trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx or not ctx.is_valid or ctx.trace_id == 0:
        return None
    return format_otel_trace_id(ctx.trace_id)
