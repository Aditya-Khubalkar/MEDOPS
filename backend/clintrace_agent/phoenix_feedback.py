"""Log verification and eval signals back to Phoenix for the feedback loop.

Ground-truth mismatches from NHAMCS (and nurse UI overrides) are written as
trace annotations so the FeedbackAgent can detect override patterns.
"""

from typing import Any

from clintrace_agent.phoenix_annotations import (
    mirror_span_annotation,
    normalize_trace_id,
    phoenix_client,
    write_trace_annotation,
)
from clintrace_agent.trace_context import (
    clinical_phrases_from_text,
    extract_chief_complaint_from_text,
    normalize_chief_complaint,
    search_keywords_from_intake,
)


def _log_annotation(
    trace_id: str,
    *,
    name: str,
    annotator_kind: str,
    label: str,
    score: float,
    explanation: str,
    metadata: dict[str, Any] | None = None,
    mirror_to_span: bool = False,
) -> dict[str, Any] | None:
    """Write trace annotation; optionally mirror to root span for Phoenix UI."""
    client = phoenix_client()
    if client is None or not normalize_trace_id(trace_id):
        return None

    inserted = write_trace_annotation(
        client,
        trace_id=trace_id,
        name=name,
        annotator_kind=annotator_kind,  # type: ignore[arg-type]
        label=label,
        score=score,
        explanation=explanation,
        metadata=metadata,
        sync=True,
    )
    if mirror_to_span:
        mirror_span_annotation(
            client,
            trace_id=trace_id,
            name=name,
            annotator_kind=annotator_kind,  # type: ignore[arg-type]
            label=label,
            score=score,
            explanation=explanation,
            metadata=metadata,
        )
    return inserted


def log_ground_truth_annotation(
    trace_id: str,
    *,
    ground_truth_esi: int,
    predicted_esi: int | None,
    source: str,
    record_id: str | None = None,
    parsed_symptoms: str | dict | None = None,
    patient_input: str | None = None,
) -> None:
    """Log nurse-assigned ESI vs model prediction to Phoenix."""
    if predicted_esi is None:
        label = "extraction_failed"
        score = 0.0
        explanation = (
            f"Could not extract ESI from audit report. "
            f"Ground truth ESI-{ground_truth_esi} ({source})."
        )
    elif predicted_esi == ground_truth_esi:
        label = "ground_truth_match"
        score = 1.0
        explanation = (
            f"Predicted ESI-{predicted_esi} matches ground truth "
            f"ESI-{ground_truth_esi} ({source})."
        )
    else:
        delta = predicted_esi - ground_truth_esi
        if delta > 0:
            label = "under_triage"
            score = 0.0
            severity = "SAFETY: model scored lower acuity than nurse"
        else:
            label = "over_triage"
            score = 0.5
            severity = "Model scored higher acuity than nurse"
        explanation = (
            f"{severity}. Predicted ESI-{predicted_esi}, "
            f"ground truth ESI-{ground_truth_esi} ({source})."
        )

    metadata: dict[str, Any] = {
        "source": source,
        "ground_truth_esi": ground_truth_esi,
        "predicted_esi": predicted_esi,
    }
    if record_id:
        metadata["record_id"] = record_id
    similarity_source = parsed_symptoms
    if similarity_source is None and patient_input:
        similarity_source = {"chief_complaint": patient_input[:200], "symptoms": []}
    if similarity_source is not None:
        keywords = symptom_keywords_from_parsed(similarity_source)
        if keywords:
            metadata["chief_complaint"] = keywords[0]
            metadata["symptom_keywords"] = keywords

    _log_annotation(
        trace_id,
        name="ground_truth_eval",
        annotator_kind="LLM",
        label=label,
        score=score,
        explanation=explanation,
        metadata=metadata,
        mirror_to_span=True,
    )


def log_diagnosis_annotation(
    trace_id: str,
    *,
    diag_result: dict[str, Any],
) -> None:
    """Log post-hoc diagnosis consistency eval (NHAMCS DIAG* vs triage)."""
    _log_annotation(
        trace_id,
        name="diagnosis_consistency",
        annotator_kind="LLM",
        label=diag_result.get("diag_consistency_label", "unknown"),
        score=float(diag_result.get("diag_consistency_score") or 0.0),
        explanation=diag_result.get("diag_explanation", ""),
    )


def log_quality_annotation(
    trace_id: str,
    *,
    eval_result: dict[str, Any],
) -> None:
    """Log LLM-as-judge triage quality eval to Phoenix."""
    _log_annotation(
        trace_id,
        name="triage_quality",
        annotator_kind="LLM",
        label=eval_result.get("quality_label", "unknown"),
        score=float(eval_result.get("quality_score", 0.0)),
        explanation=eval_result.get("explanation", ""),
        mirror_to_span=True,
    )


def _similarity_metadata_for_review(
    patient_input: str | None,
    chief_complaint: str | None,
) -> dict[str, Any]:
    """Build chief complaint + keywords for Phoenix override matching."""
    keywords: list[str] = []
    if chief_complaint:
        keywords.append(normalize_chief_complaint(chief_complaint))
    if patient_input:
        extracted = extract_chief_complaint_from_text(patient_input)
        if extracted:
            keywords.append(normalize_chief_complaint(extracted))
        keywords.extend(clinical_phrases_from_text(patient_input))
    seen: set[str] = set()
    unique: list[str] = []
    for kw in keywords:
        if kw and kw not in seen:
            seen.add(kw)
            unique.append(kw)
    if not unique and patient_input:
        fallback = search_keywords_from_intake(None, patient_input)
        for kw in fallback:
            if kw and kw not in seen:
                seen.add(kw)
                unique.append(kw)
    if not unique:
        return {}
    primary = unique[0]
    for candidate in unique:
        if len(candidate) <= 40:
            primary = candidate
            break
    return {
        "chief_complaint": primary,
        "symptom_keywords": unique[:8],
    }


def _nurse_review_quality_eval(
    action: str,
    *,
    agent_esi: int | None,
    nurse_esi: int | None,
    note: str = "",
) -> dict[str, Any]:
    """Build triage_quality payload for nurse approve/override."""
    if action == "approve":
        label = "nurse_confirmed"
        score = 1.0
        explanation = (
            f"Nurse approved agent ESI-{agent_esi}."
            if agent_esi is not None
            else "Nurse approved agent triage decision."
        )
    elif action == "under_triage":
        label = "dangerous"
        score = 0.0
        explanation = (
            f"Nurse override: agent ESI-{agent_esi}, "
            f"nurse ESI-{nurse_esi} (under-triage correction)."
        )
    elif action == "over_triage":
        label = "potential_risk"
        score = 0.5
        explanation = (
            f"Nurse override: agent ESI-{agent_esi}, "
            f"nurse ESI-{nurse_esi} (over-triage correction)."
        )
    else:
        label = "potential_risk"
        score = 0.5
        explanation = note or f"Nurse action: {action}"

    if note and action != "approve":
        explanation += f" Reason: {note}"
    elif note:
        explanation += f" Note: {note}"

    return {
        "quality_label": label,
        "quality_score": score,
        "explanation": explanation,
    }


def log_nurse_review(
    trace_id: str,
    *,
    action: str,
    agent_esi: int | None,
    nurse_esi: int | None = None,
    note: str = "",
    patient_input: str | None = None,
    chief_complaint: str | None = None,
) -> dict[str, Any] | None:
    """Log nurse approve/override to Phoenix (ground_truth_eval + triage_quality)."""
    if action == "approve":
        label = "nurse_approved"
        score = 1.0
        explanation = (
            f"Nurse approved agent ESI-{agent_esi}."
            if agent_esi is not None
            else "Nurse approved agent triage decision."
        )
        if note:
            explanation += f" Note: {note}"
    elif action == "under_triage":
        label = "under_triage"
        score = 0.0
        explanation = (
            f"Nurse override: agent ESI-{agent_esi}, "
            f"nurse ESI-{nurse_esi} (under-triaged)."
        )
        if note:
            explanation += f" Reason: {note}"
    elif action == "over_triage":
        label = "over_triage"
        score = 0.5
        explanation = (
            f"Nurse override: agent ESI-{agent_esi}, "
            f"nurse ESI-{nurse_esi} (over-triaged)."
        )
        if note:
            explanation += f" Reason: {note}"
    else:
        label = action
        score = 0.0
        explanation = note or f"Nurse action: {action}"

    metadata: dict[str, Any] = {
        "source": "nurse_ui",
        "action": action,
        "agent_esi": agent_esi,
    }
    if nurse_esi is not None:
        metadata["nurse_esi"] = nurse_esi
    if note:
        metadata["note"] = note
        metadata["nurse_note"] = note
    metadata.update(
        _similarity_metadata_for_review(patient_input, chief_complaint)
    )

    inserted = _log_annotation(
        trace_id,
        name="ground_truth_eval",
        annotator_kind="HUMAN",
        label=label,
        score=score,
        explanation=explanation,
        metadata=metadata,
        mirror_to_span=True,
    )
    if inserted is None:
        return None

    quality = _nurse_review_quality_eval(
        action,
        agent_esi=agent_esi,
        nurse_esi=nurse_esi,
        note=note,
    )
    _log_annotation(
        trace_id,
        name="triage_quality",
        annotator_kind="HUMAN",
        label=quality["quality_label"],
        score=float(quality["quality_score"]),
        explanation=quality["explanation"],
        mirror_to_span=True,
    )
    return inserted
