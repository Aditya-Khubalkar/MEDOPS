"""OpenTelemetry / Phoenix trace metadata for triage similarity search.

Stamps filterable span attributes on the root ``clinictrace.triage`` span so
Phoenix ``get_spans(attributes=...)`` can find historically similar cases.
"""

from __future__ import annotations

import re
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from clintrace_agent.json_utils import parse_json_blob

try:
    from openinference.semconv.trace import (
        OpenInferenceMimeTypeValues,
        OpenInferenceSpanKindValues,
        SpanAttributes,
    )
except ImportError:  # pragma: no cover - optional at import time
    OpenInferenceMimeTypeValues = None  # type: ignore[misc, assignment]
    OpenInferenceSpanKindValues = None  # type: ignore[misc, assignment]
    SpanAttributes = None  # type: ignore[misc, assignment]

# Filterable span attributes (Phoenix >= 14.9 attribute queries).
ATTR_CHIEF_COMPLAINT = "clinictrace.chief_complaint"
ATTR_SYMPTOM_KEYWORDS = "clinictrace.symptom_keywords"
ATTR_ESI_LEVEL = "clinictrace.esi_level"
ATTR_TRIAGE_SPAN_NAME = "clinictrace.triage"

ROOT_SPAN_NAME = "clinictrace.triage"

_CHIEF_COMPLAINT_RE = re.compile(
    r"chief complaint:\s*([^.\n;]+)",
    re.IGNORECASE,
)
_MAX_SEARCH_KEYWORD_LEN = 80

# Multi-word phrases checked in order (longest first) for intake/override matching.
_CLINICAL_PHRASES: tuple[str, ...] = (
    "crushing chest pain",
    "chest pain radiating to left arm",
    "chest pain",
    "shortness of breath",
    "difficulty breathing",
    "abdominal pain",
    "altered mental status",
    "syncope",
    "diaphoresis",
    "nausea",
    "headache",
    "stroke",
    "seizure",
    "weakness",
    "fever",
    "bleeding",
)


def clinical_phrases_from_text(text: str) -> list[str]:
    """Extract normalized clinical phrases present in free-text intake."""
    if not text:
        return []
    lowered = text.lower()
    found: list[str] = []
    seen: set[str] = set()
    for phrase in _CLINICAL_PHRASES:
        if phrase in lowered:
            normalized = normalize_chief_complaint(phrase)
            if normalized not in seen:
                seen.add(normalized)
                found.append(normalized)
    return found


def normalize_chief_complaint(text: str) -> str:
    """Normalize chief complaint for exact attribute matching."""
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    return cleaned[:120]


def extract_chief_complaint_from_text(text: str) -> str | None:
    """Pull a short chief complaint label from NHAMCS-style intake text."""
    if not text:
        return None
    match = _CHIEF_COMPLAINT_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


def _compact_keyword(text: str) -> str:
    """Prefer a short chief-complaint label over a long intake blob."""
    extracted = extract_chief_complaint_from_text(text)
    if extracted:
        return normalize_chief_complaint(extracted)
    compact = normalize_chief_complaint(text)
    if len(compact) > _MAX_SEARCH_KEYWORD_LEN:
        return compact[:_MAX_SEARCH_KEYWORD_LEN].rsplit(" ", 1)[0]
    return compact


def symptom_keywords_from_parsed(parsed_symptoms: Any) -> list[str]:
    """Extract searchable keywords from parsed_symptoms JSON."""
    data = parse_json_blob(parsed_symptoms)
    keywords: list[str] = []
    chief = data.get("chief_complaint") or data.get("chiefComplaint")
    if chief:
        keywords.append(_compact_keyword(str(chief)))
    for item in data.get("symptoms") or []:
        if item:
            keywords.append(normalize_chief_complaint(str(item))[:80])
    # Stable dedupe preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        if kw and kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique[:8]


def search_keywords_from_intake(
    parsed_symptoms: Any,
    patient_input: str | None = None,
) -> list[str]:
    """Build Phoenix similarity keywords from parser output or intake text."""
    keywords = symptom_keywords_from_parsed(parsed_symptoms)
    if keywords:
        return keywords
    if patient_input:
        extracted = extract_chief_complaint_from_text(patient_input)
        if extracted:
            return [normalize_chief_complaint(extracted)]
        phrases = clinical_phrases_from_text(patient_input)
        if phrases:
            return phrases
        return [_compact_keyword(patient_input)]
    return []


def build_trace_attributes(
    parsed_symptoms: Any,
    severity_score: Any | None = None,
) -> dict[str, str]:
    """Build Phoenix-filterable string attributes for the triage root span."""
    keywords = symptom_keywords_from_parsed(parsed_symptoms)
    attrs: dict[str, str] = {}
    if keywords:
        attrs[ATTR_CHIEF_COMPLAINT] = keywords[0]
        attrs[ATTR_SYMPTOM_KEYWORDS] = ",".join(keywords)
    severity = parse_json_blob(severity_score)
    esi = severity.get("esi_level")
    if esi is not None:
        attrs[ATTR_ESI_LEVEL] = str(int(esi))
    return attrs


def stamp_triage_root_span_start(
    span: trace.Span,
    *,
    patient_input: str,
    session_id: str,
) -> None:
    """Apply OpenInference attributes when the triage root span opens."""
    if not span.is_recording() or SpanAttributes is None:
        return
    span.set_attribute(
        SpanAttributes.OPENINFERENCE_SPAN_KIND,
        OpenInferenceSpanKindValues.CHAIN.value,
    )
    span.set_attribute(SpanAttributes.INPUT_VALUE, patient_input[:8000])
    span.set_attribute(
        SpanAttributes.INPUT_MIME_TYPE,
        OpenInferenceMimeTypeValues.TEXT.value,
    )
    span.set_attribute(SpanAttributes.SESSION_ID, session_id)
    preview = _compact_keyword(patient_input[:200])
    if preview:
        span.set_attribute(ATTR_CHIEF_COMPLAINT, preview)


def stamp_triage_root_span_end(
    span: trace.Span,
    *,
    audit_report: str,
    parsed_symptoms: Any | None = None,
    severity_score: Any | None = None,
    ok: bool = True,
) -> None:
    """Finalize OpenInference attributes on the triage root span."""
    if not span.is_recording():
        return
    if SpanAttributes is not None and audit_report:
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, audit_report[:8000])
        span.set_attribute(
            SpanAttributes.OUTPUT_MIME_TYPE,
            OpenInferenceMimeTypeValues.TEXT.value,
        )
    if parsed_symptoms is not None or severity_score is not None:
        stamp_current_span_attributes(parsed_symptoms, severity_score)
    span.set_status(
        Status(StatusCode.OK if ok else StatusCode.ERROR)
    )


def stamp_current_span_attributes(
    parsed_symptoms: Any,
    severity_score: Any | None = None,
) -> dict[str, str]:
    """Set triage metadata on the active span (usually clinictrace.triage)."""
    attrs = build_trace_attributes(parsed_symptoms, severity_score)
    span = trace.get_current_span()
    if span.is_recording() and attrs:
        for key, value in attrs.items():
            span.set_attribute(key, value)
    return attrs


def format_otel_trace_id(trace_id: int) -> str:
    """Format OTel trace id as 32-char lowercase hex."""
    return format(trace_id, "032x")


def current_otel_trace_id() -> str | None:
    """Return the active span's OTel trace id, if recording."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx or not ctx.is_valid or ctx.trace_id == 0:
        return None
    return format_otel_trace_id(ctx.trace_id)


def keyword_overlap_score(query: list[str], candidate: str) -> float:
    """Score overlap between query keywords and a comma-separated attribute."""
    if not query or not candidate:
        return 0.0
    cand = {k.strip() for k in candidate.split(",") if k.strip()}
    query_set = set(query)
    if not cand or not query_set:
        return 0.0
    intersection = len(query_set & cand)
    union = len(query_set | cand)
    return intersection / union if union else 0.0
