"""Phoenix REST helpers for the feedback loop (low-latency path)."""

from __future__ import annotations

import json
from typing import Any

from google.adk.tools import FunctionTool
from opentelemetry import trace

from clintrace_agent.config import PHOENIX_PROJECT
from clintrace_agent.feedback_matching import (
    OVERRIDE_LABELS,
    annotation_matches_case,
    calibration_allowed,
)
from clintrace_agent.phoenix_annotations import fetch_trace_annotations, phoenix_client
from clintrace_agent.tools.feedback_query import compute_confidence_adjustment
from clintrace_agent.trace_context import (
    ATTR_CHIEF_COMPLAINT,
    ATTR_SYMPTOM_KEYWORDS,
    ROOT_SPAN_NAME,
    _compact_keyword,
    extract_chief_complaint_from_text,
    keyword_overlap_score,
    normalize_chief_complaint,
    search_keywords_from_intake,
)

try:
    from openinference.semconv.trace import (
        OpenInferenceSpanKindValues,
        SpanAttributes,
    )
except ImportError:  # pragma: no cover
    OpenInferenceSpanKindValues = None  # type: ignore[misc, assignment]
    SpanAttributes = None  # type: ignore[misc, assignment]

_phoenix_tool_tracer = trace.get_tracer("clinictrace.phoenix")

_OVERRIDE_LABELS = OVERRIDE_LABELS

_MIN_SIMILAR_FOR_CONFIDENCE = 3
_MAX_SEARCH_KEYWORD_LEN = 80


def _span_attribute(span: Any, key: str) -> str | None:
    if isinstance(span, dict):
        attrs = span.get("attributes") or {}
    else:
        attrs = getattr(span, "attributes", None) or {}
    if not isinstance(attrs, dict):
        return None
    val = attrs.get(key)
    return str(val) if val is not None else None


def _span_trace_id(span: Any) -> str | None:
    if isinstance(span, dict):
        ctx = span.get("context") or {}
        tid = ctx.get("trace_id")
    else:
        ctx = getattr(span, "context", None) or {}
        tid = getattr(ctx, "trace_id", None) if ctx else None
    if not tid:
        return None
    text = str(tid).strip().lower().replace("-", "")
    return text if len(text) == 32 else None


def _annotation_metadata(meta: Any) -> dict[str, Any]:
    return meta if isinstance(meta, dict) else {}


def _normalize_span_chief(value: str) -> str:
    """Compact stored span chief complaint for overlap scoring."""
    if len(value) > _MAX_SEARCH_KEYWORD_LEN:
        extracted = extract_chief_complaint_from_text(value)
        if extracted:
            return normalize_chief_complaint(extracted)
        return _compact_keyword(value)
    return normalize_chief_complaint(value)


def _count_overrides_from_annotations(
    annotations: list[dict[str, Any]],
    *,
    trace_ids: list[str],
    keywords: list[str],
    match_method: str | None = None,
) -> tuple[int, int]:
    """Count complaint-matched override annotations across similar trace ids."""
    override_traces: set[str] = set()
    for ann in annotations:
        name = ann.get("name", "")
        label = ann.get("label", "")
        tid = ann.get("trace_id")
        meta = _annotation_metadata(ann.get("metadata") or {})
        if (
            name == "ground_truth_eval"
            and label in _OVERRIDE_LABELS
            and tid
            and annotation_matches_case(
                meta, keywords, match_method=match_method
            )
        ):
            override_traces.add(str(tid))
    return len(override_traces), len(trace_ids)


def _nurse_corrections_from_annotations(
    annotations: list[dict[str, Any]],
    *,
    keywords: list[str],
    match_method: str | None = None,
) -> list[dict[str, Any]]:
    """Extract nurse ESI corrections for clinically similar cases only."""
    corrections: list[dict[str, Any]] = []
    for ann in annotations:
        name = ann.get("name", "")
        label = ann.get("label", "")
        if name != "ground_truth_eval" or label not in _OVERRIDE_LABELS:
            continue
        meta = _annotation_metadata(ann.get("metadata") or {})
        if not annotation_matches_case(meta, keywords, match_method=match_method):
            continue
        nurse_esi = meta.get("nurse_esi")
        note = (meta.get("nurse_note") or meta.get("note") or "").strip()
        if nurse_esi is None:
            continue
        try:
            corrections.append(
                {
                    "nurse_esi": int(nurse_esi),
                    "agent_esi": meta.get("agent_esi"),
                    "label": label,
                    "source": meta.get("source", "unknown"),
                    "nurse_note": note or None,
                    "trace_id": ann.get("trace_id"),
                    "chief_complaint": meta.get("chief_complaint"),
                }
            )
        except (TypeError, ValueError):
            continue
    return list(reversed(corrections))


def _consensus_nurse_esi(corrections: list[dict[str, Any]]) -> int | None:
    """Pick nurse ESI from the most recent similar-case override."""
    if not corrections:
        return None
    return corrections[0]["nurse_esi"]


def _nurse_notes_from_annotations(
    annotations: list[dict[str, Any]],
    *,
    keywords: list[str],
    match_method: str | None = None,
) -> list[str]:
    """Collect nurse notes from complaint-matched override annotations."""
    notes: list[str] = []
    seen: set[str] = set()
    for ann in annotations:
        if ann.get("name") != "ground_truth_eval":
            continue
        meta = _annotation_metadata(ann.get("metadata") or {})
        if not annotation_matches_case(meta, keywords, match_method=match_method):
            continue
        note = (meta.get("nurse_note") or meta.get("note") or "").strip()
        if note and note not in seen:
            seen.add(note)
            notes.append(note)
    return notes[:5]


def _fetch_annotations_for_trace_ids(
    client: Any,
    trace_ids: list[str],
) -> list[dict[str, Any]]:
    """Load trace annotations via Phoenix REST (nested result schema)."""
    if not trace_ids:
        return []
    unique_ids = list(dict.fromkeys(trace_ids))[:50]
    try:
        return fetch_trace_annotations(client, unique_ids, limit=200)
    except Exception:  # noqa: BLE001
        return []


def _trace_otel_id(trace: Any) -> str | None:
    if isinstance(trace, dict):
        ctx = trace.get("context") or {}
        tid = ctx.get("trace_id") or trace.get("trace_id") or trace.get("id")
    else:
        ctx = getattr(trace, "context", None) or {}
        tid = getattr(ctx, "trace_id", None) if ctx else None
        if not tid:
            tid = getattr(trace, "id", None)
    if not tid:
        return None
    text = str(tid).strip().lower().replace("-", "")
    return text if len(text) == 32 else None


def _find_similar_trace_ids(
    client: Any,
    keywords: list[str],
    *,
    scan_limit: int = 80,
    min_overlap: float = 0.2,
) -> tuple[list[str], str]:
    """Find trace ids for cases similar to current symptoms.

    Returns:
        (trace_ids, match_method) where match_method describes how matches were found.
    """
    if not keywords:
        return [], "none"

    primary = keywords[0]

    # 1) Exact chief-complaint attribute match on root triage span
    try:
        exact_ids: list[str] = []
        for kw in keywords[:4]:
            exact_spans = client.spans.get_spans(
                project_identifier=PHOENIX_PROJECT,
                name=ROOT_SPAN_NAME,
                attributes={ATTR_CHIEF_COMPLAINT: kw},
                limit=scan_limit,
            )
            for span in exact_spans:
                tid = _span_trace_id(span)
                if tid:
                    exact_ids.append(tid)
        if exact_ids:
            return list(dict.fromkeys(exact_ids)), "attribute_chief_complaint"
    except Exception:  # noqa: BLE001 — attribute API may be unavailable
        pass

    # 2) Root triage spans: rank by symptom keyword overlap
    try:
        root_spans = client.spans.get_spans(
            project_identifier=PHOENIX_PROJECT,
            name=ROOT_SPAN_NAME,
            limit=scan_limit,
        )
    except Exception:  # noqa: BLE001
        root_spans = []

    scored: list[tuple[float, str]] = []
    for span in root_spans:
        tid = _span_trace_id(span)
        if not tid:
            continue
        kw_attr = _span_attribute(span, ATTR_SYMPTOM_KEYWORDS) or ""
        chief_attr = _span_attribute(span, ATTR_CHIEF_COMPLAINT) or ""
        if chief_attr:
            chief_attr = _normalize_span_chief(chief_attr)
        score = keyword_overlap_score(keywords, kw_attr)
        if chief_attr and chief_attr == primary:
            score = max(score, 1.0)
        if score >= min_overlap:
            scored.append((score, tid))

    scored.sort(key=lambda x: x[0], reverse=True)
    if scored:
        return [tid for _, tid in scored[:30]], "keyword_overlap"

    # 3) Annotation metadata fallback (verification runs)
    return _trace_ids_from_annotation_metadata(client, keywords, limit=scan_limit)


def _recent_trace_ids(client: Any, *, limit: int) -> list[str]:
    """Return recent OTel trace ids for annotation scans."""
    try:
        recent = client.traces.get_traces(
            project_identifier=PHOENIX_PROJECT,
            limit=limit,
            order="desc",
        )
    except Exception:  # noqa: BLE001
        return []
    ids: list[str] = []
    for recent_trace in recent:
        tid = _trace_otel_id(recent_trace)
        if tid:
            ids.append(tid)
    return ids


def _trace_ids_from_annotation_metadata(
    client: Any,
    keywords: list[str],
    *,
    limit: int,
) -> tuple[list[str], str]:
    """Match traces whose ground_truth_eval metadata mentions similar complaints."""
    try:
        recent = client.traces.get_traces(
            project_identifier=PHOENIX_PROJECT,
            limit=limit,
            order="desc",
        )
    except Exception:  # noqa: BLE001
        return [], "recent_fallback"

    trace_ids = [
        tid for trace in recent if (tid := _trace_otel_id(trace)) is not None
    ]
    annotations = _fetch_annotations_for_trace_ids(client, trace_ids[:limit])
    matched: list[str] = []
    for ann in annotations:
        if ann.get("name") != "ground_truth_eval":
            continue
        meta = ann.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        tid = ann.get("trace_id")
        if not tid:
            continue
        chief = meta.get("chief_complaint") or meta.get("chiefComplaint")
        if chief and annotation_matches_case(
            meta, keywords, match_method="annotation_metadata"
        ):
            matched.append(str(tid))
            continue
        ann_keywords = meta.get("symptom_keywords") or []
        if isinstance(ann_keywords, str):
            ann_keywords = [k.strip() for k in ann_keywords.split(",")]
        if ann_keywords and annotation_matches_case(
            meta, keywords, match_method="annotation_metadata"
        ):
            matched.append(str(tid))

    if matched:
        return list(dict.fromkeys(matched)), "annotation_metadata"
    return [], "recent_fallback"


def query_phoenix_feedback(
    parsed_symptoms: str,
    current_confidence: float,
    limit: int = 30,
    *,
    current_esi: int | None = None,
    patient_input: str | None = None,
) -> dict[str, Any]:
    """Query Phoenix for similar cases and adjust confidence from override history.

    Uses span attribute filters when available, then keyword overlap on
    ``clinictrace.*`` attributes stamped by ``trace_context.stamp_current_span_attributes``.
    When a similar case has a nurse ESI override, returns ``calibrated_esi`` so the
    audit report can reflect the corrected acuity.

    Args:
        parsed_symptoms: JSON string from the symptom parser output_key.
        current_confidence: Model confidence from severity_score (0.0-1.0).
        limit: Max similar traces to consider.
        current_esi: Model-predicted ESI level (1-5), if known.
        patient_input: Raw intake text for keyword fallback matching.

    Returns:
        Feedback JSON including adjusted_confidence, calibrated_esi, and
        historical_insight.
    """
    client = phoenix_client()
    keywords = search_keywords_from_intake(parsed_symptoms, patient_input)
    if client is None:
        adjusted = compute_confidence_adjustment(0, 0, current_confidence)
        return {
            "similar_cases_found": 0,
            "override_count": 0,
            "symptom_keywords": keywords,
            "match_method": "none",
            "data_source": "none",
            **adjusted,
            "historical_insight": (
                "Phoenix not configured; using severity confidence only."
            ),
        }

    with _phoenix_tool_tracer.start_as_current_span(
        "phoenix.query_feedback"
    ) as span:
        if span.is_recording() and SpanAttributes is not None:
            span.set_attribute(
                SpanAttributes.OPENINFERENCE_SPAN_KIND,
                OpenInferenceSpanKindValues.TOOL.value,
            )
            span.set_attribute(SpanAttributes.TOOL_NAME, "query_phoenix_feedback")
            span.set_attribute(
                SpanAttributes.INPUT_VALUE,
                json.dumps(
                    {
                        "parsed_symptoms": parsed_symptoms[:500],
                        "current_confidence": current_confidence,
                        "limit": limit,
                    }
                ),
            )
        result = _query_phoenix_feedback_inner(
            client,
            parsed_symptoms=parsed_symptoms,
            current_confidence=current_confidence,
            current_esi=current_esi,
            keywords=keywords,
            limit=limit,
        )
        if span.is_recording() and SpanAttributes is not None:
            span.set_attribute(
                SpanAttributes.OUTPUT_VALUE,
                json.dumps(result)[:4000],
            )
    return result


def _query_phoenix_feedback_inner(
    client: Any,
    *,
    parsed_symptoms: str,
    current_confidence: float,
    current_esi: int | None,
    keywords: list[str],
    limit: int,
) -> dict[str, Any]:
    """Phoenix REST lookup (called inside TOOL span)."""
    try:
        trace_ids, match_method = _find_similar_trace_ids(
            client, keywords, scan_limit=max(limit * 3, 60)
        )
        similar_ids = trace_ids[:limit] if trace_ids else []
        annotation_ids = list(
            dict.fromkeys(
                similar_ids
                + _recent_trace_ids(client, limit=max(limit, 40))
            )
        )[:50]
        annotations = _fetch_annotations_for_trace_ids(client, annotation_ids)
        corrections = _nurse_corrections_from_annotations(
            annotations,
            keywords=keywords,
            match_method=match_method,
        )
        if corrections and not similar_ids:
            similar_ids = list(
                dict.fromkeys(
                    str(c["trace_id"])
                    for c in corrections
                    if c.get("trace_id")
                )
            )[:limit]
            match_method = "annotation_metadata"
        elif not similar_ids:
            match_method = "none"
    except Exception as exc:  # noqa: BLE001
        adjusted = compute_confidence_adjustment(0, 0, current_confidence)
        return {
            "similar_cases_found": 0,
            "override_count": 0,
            "symptom_keywords": keywords,
            "match_method": "error",
            "data_source": "phoenix_rest_error",
            **adjusted,
            "historical_insight": f"Phoenix query failed: {exc}",
        }

    override_count, total_similar = _count_overrides_from_annotations(
        annotations,
        trace_ids=similar_ids,
        keywords=keywords,
        match_method=match_method,
    )
    if total_similar == 0 and similar_ids:
        total_similar = len(similar_ids)
    nurse_esi = _consensus_nurse_esi(corrections)
    nurse_notes = _nurse_notes_from_annotations(
        annotations,
        keywords=keywords,
        match_method=match_method,
    )

    calibrated_esi: int | None = None
    esi_calibration_applied = False
    calibration_reason: str | None = None
    if nurse_esi is not None and calibration_allowed(match_method):
        calibrated_esi = nurse_esi
        esi_calibration_applied = True
        label = corrections[0].get("label", "override").replace("_", " ")
        calibration_reason = (
            f"Phoenix nurse override on similar case: corrected to ESI "
            f"{nurse_esi} ({label})."
        )
        if corrections[0].get("nurse_note"):
            calibration_reason += f" Nurse note: {corrections[0]['nurse_note']}"
        if current_esi is not None and nurse_esi != current_esi:
            calibration_reason += (
                f" Model scored ESI {current_esi} on this run."
            )

    # If attribute match found too few cases, note low sample size in adjustment
    if (
        match_method != "recent_fallback"
        and total_similar < _MIN_SIMILAR_FOR_CONFIDENCE
        and total_similar > 0
    ):
        match_method = f"{match_method}_low_n"

    adjusted = compute_confidence_adjustment(
        override_count, total_similar, current_confidence
    )
    kw_hint = ", ".join(keywords[:3]) if keywords else "general"
    if total_similar == 0:
        insight = (
            f"No similar Phoenix cases found for {kw_hint}; "
            "nurse overrides from other presentations were not applied."
        )
    else:
        insight = (
            f"Found {total_similar} similar case(s) via {match_method} "
            f"({kw_hint}); {override_count} complaint-matched nurse overrides."
        )
    if esi_calibration_applied and calibrated_esi is not None:
        insight += f" Applying nurse-corrected ESI {calibrated_esi} from history."
    if nurse_notes:
        insight += f" Prior nurse note(s): {' | '.join(nurse_notes[:2])}"
    return {
        "similar_cases_found": total_similar,
        "override_count": override_count,
        "symptom_keywords": keywords,
        "match_method": match_method,
        "data_source": "phoenix_rest",
        "model_esi": current_esi,
        "calibrated_esi": calibrated_esi,
        "nurse_corrected_esi": nurse_esi,
        "esi_calibration_applied": esi_calibration_applied,
        "calibration_reason": calibration_reason,
        "nurse_notes_from_history": nurse_notes,
        **adjusted,
        "historical_insight": insight,
    }


phoenix_feedback_tool = FunctionTool(func=query_phoenix_feedback)
