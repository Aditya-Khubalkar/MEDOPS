"""Phoenix trace/span annotation helpers (correct API schema + fetch)."""

from __future__ import annotations

import os
from typing import Any, Literal

from .config import PHOENIX_PROJECT
from .trace_context import ROOT_SPAN_NAME

AnnotatorKind = Literal["LLM", "CODE", "HUMAN"]


def normalize_trace_id(trace_id: str) -> str | None:
    """Return 32-char OTel trace id hex, or None if invalid."""
    if not trace_id:
        return None
    text = str(trace_id).strip().lower().replace("-", "")
    if len(text) == 32 and all(c in "0123456789abcdef" for c in text):
        return text
    return None


def phoenix_client():
    """Build Phoenix REST client from environment."""
    from phoenix.client import Client

    base_url = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "").rstrip("/")
    api_key = os.getenv("PHOENIX_API_KEY", "")
    if not base_url or not api_key:
        return None
    return Client(base_url=base_url, api_key=api_key)


def flatten_trace_annotation(ann: dict[str, Any]) -> dict[str, Any]:
    """Normalize Phoenix trace annotation to flat label/score/explanation."""
    result = ann.get("result") or {}
    if not isinstance(result, dict):
        result = {}
    metadata = ann.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "name": ann.get("name", ""),
        "label": result.get("label"),
        "score": result.get("score"),
        "explanation": result.get("explanation"),
        "metadata": metadata,
        "trace_id": ann.get("trace_id"),
    }


def fetch_trace_annotations(
    client: Any,
    trace_ids: list[str],
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Load trace annotations for one or more OTel trace ids."""
    ids = []
    for tid in trace_ids:
        normalized = normalize_trace_id(tid)
        if normalized:
            ids.append(normalized)
    if not ids:
        return []

    path = f"v1/projects/{PHOENIX_PROJECT}/trace_annotations"
    response = client._client.get(  # noqa: SLF001 — official REST path
        url=path,
        params={"trace_ids": ids, "limit": limit},
    )
    response.raise_for_status()
    payload = response.json()
    raw = payload.get("data") or []
    return [flatten_trace_annotation(a) for a in raw if isinstance(a, dict)]


_ROOT_SPAN_FALLBACK_NAMES = (
    ROOT_SPAN_NAME,
    "phoenix.query_feedback",
    "agent_run",
    "invoke_agent",
)


def find_root_span_id(client: Any, trace_id: str) -> str | None:
    """Find a root-ish span id for mirroring annotations in Phoenix UI."""
    normalized = normalize_trace_id(trace_id)
    if not normalized:
        return None

    for span_name in _ROOT_SPAN_FALLBACK_NAMES:
        try:
            spans = client.spans.get_spans(
                project_identifier=PHOENIX_PROJECT,
                name=span_name,
                trace_ids=[normalized],
                limit=1,
            )
        except Exception:  # noqa: BLE001
            spans = []
        if spans:
            ctx = spans[0].get("context") or {}
            span_id = ctx.get("span_id")
            if span_id:
                return span_id

    try:
        spans = client.spans.get_spans(
            project_identifier=PHOENIX_PROJECT,
            trace_ids=[normalized],
            limit=20,
        )
    except Exception:  # noqa: BLE001
        return None

    earliest: tuple[str | None, str | None] | None = None
    for span in spans:
        if not isinstance(span, dict):
            continue
        ctx = span.get("context") or {}
        tid = str(ctx.get("trace_id", "")).lower().replace("-", "")
        if tid != normalized:
            continue
        span_id = ctx.get("span_id")
        if not span_id:
            continue
        start = span.get("start_time") or ""
        if earliest is None or str(start) < str(earliest[0]):
            earliest = (start, span_id)
    return earliest[1] if earliest else None


def write_trace_annotation(
    client: Any,
    *,
    trace_id: str,
    name: str,
    annotator_kind: AnnotatorKind,
    label: str | None = None,
    score: float | None = None,
    explanation: str | None = None,
    metadata: dict[str, Any] | None = None,
    sync: bool = True,
) -> dict[str, Any] | None:
    """Write a trace annotation using the Phoenix client helper (result nested)."""
    normalized = normalize_trace_id(trace_id)
    if not normalized:
        raise ValueError(f"Invalid OTel trace id: {trace_id!r}")

    inserted = client.traces.add_trace_annotation(
        trace_id=normalized,
        annotation_name=name,
        annotator_kind=annotator_kind,
        label=label,
        score=score,
        explanation=explanation,
        metadata=metadata,
        sync=sync,
    )
    return dict(inserted) if inserted else None


def mirror_span_annotation(
    client: Any,
    *,
    trace_id: str,
    name: str,
    annotator_kind: AnnotatorKind,
    label: str | None = None,
    score: float | None = None,
    explanation: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Mirror trace annotation onto the root span (visible in span Annotations tab)."""
    span_id = find_root_span_id(client, trace_id)
    if not span_id:
        return
    client.spans.add_span_annotation(
        span_id=span_id,
        annotation_name=name,
        annotator_kind=annotator_kind,
        label=label,
        score=score,
        explanation=explanation,
        metadata=metadata,
        sync=True,
    )
