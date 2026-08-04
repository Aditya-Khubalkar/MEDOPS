"""Build structured triage actions from workflow session state.

Turns pipeline outputs into nurse-facing action cards (routing orders,
alerts, human-review flags) rather than report text alone.
"""

from __future__ import annotations

from typing import Any

from clintrace_agent.json_utils import parse_json_blob
from clintrace_agent.report_extract import (
    extract_confidence_from_report,
    extract_destination_from_report,
    extract_esi_from_report,
    extract_feedback_from_report,
    extract_priority_from_report,
)
from clintrace_agent.routing_fallback import complete_routing_from_state

_MISSION_STEPS = (
    ("parse_intake", "Parse intake"),
    ("score_severity", "Score severity (ESI)"),
    ("screen_red_flags", "Screen red flags"),
    ("route_patient", "Route patient"),
    ("phoenix_history", "Phoenix history check"),
    ("compose_actions", "Compose actions"),
)


def _activation_for_condition(condition: str) -> str | None:
    """Map red-flag condition to ED activation team label."""
    key = condition.lower().replace(" ", "_")
    mapping = {
        "stroke": "stroke_team",
        "stemi": "cath_lab",
        "acs": "cath_lab",
        "sepsis": "sepsis_bundle",
        "anaphylaxis": "code_anaphylaxis",
        "pe": "pe_pathway",
        "pulmonary_embolism": "pe_pathway",
    }
    for prefix, team in mapping.items():
        if prefix in key:
            return team
    return None


def build_mission_plan(*, complete: bool = True) -> dict[str, Any]:
    """Return the clinical protocol steps for UI progress display."""
    status = "complete" if complete else "in_progress"
    return {
        "name": "ed_triage",
        "steps": [
            {"id": step_id, "label": label, "status": status}
            for step_id, label in _MISSION_STEPS
        ],
    }


def build_triage_actions(
    state: dict[str, Any],
    *,
    audit_report: str | None = None,
) -> dict[str, Any]:
    """Compose structured actions from workflow session state.

    Args:
        state: ADK session state after triage pipeline completes.
        audit_report: Final audit text — used when JSON state keys are missing.

    Returns:
        JSON-serializable action payload for UI and audit.
    """
    parsed = parse_json_blob(state.get("parsed_symptoms"))
    severity = parse_json_blob(state.get("severity_score"))
    red_flags = parse_json_blob(state.get("red_flags"))
    routing = complete_routing_from_state(state)
    feedback = parse_json_blob(state.get("feedback_analysis"))

    if audit_report:
        report_feedback = extract_feedback_from_report(audit_report)
        for key, value in report_feedback.items():
            if key not in feedback or feedback.get(key) in (None, 0, "", False, []):
                feedback[key] = value

    esi = severity.get("esi_level")
    esi_conf = severity.get("confidence", 0.0)
    if audit_report:
        if esi is None:
            esi = extract_esi_from_report(audit_report)
        if not esi_conf:
            parsed_conf = extract_confidence_from_report(audit_report)
            if parsed_conf is not None:
                esi_conf = parsed_conf
    if feedback.get("model_esi") is not None:
        esi = feedback.get("model_esi")
    adjusted = feedback.get("adjusted_confidence", esi_conf)
    display_esi = feedback.get("calibrated_esi") or esi
    esi_calibrated = bool(feedback.get("esi_calibration_applied"))

    recommend_review = bool(feedback.get("recommend_human_review", False))
    if display_esi in (1, 2):
        recommend_review = True
    try:
        if float(esi_conf) < 0.7:
            recommend_review = True
    except (TypeError, ValueError):
        pass

    review_reasons: list[str] = []
    if display_esi in (1, 2):
        review_reasons.append(
            f"ESI level {display_esi} requires immediate attention"
        )
    try:
        if float(adjusted) < 0.7:
            review_reasons.append(
                f"Adjusted confidence {_pct(adjusted)} below threshold"
            )
    except (TypeError, ValueError):
        pass
    override_count = int(feedback.get("override_count") or 0)
    similar = int(feedback.get("similar_cases_found") or 0)
    if override_count > 0 and similar > 0:
        rate = override_count / similar
        if rate > 0.15:
            review_reasons.append(
                f"{override_count}/{similar} similar cases had nurse overrides"
            )

    alerts: list[dict[str, Any]] = []
    for flag in red_flags.get("red_flags_detected") or []:
        if not isinstance(flag, dict):
            continue
        condition = str(flag.get("condition", "unknown"))
        alerts.append(
            {
                "type": "red_flag",
                "condition": condition,
                "urgency": flag.get("urgency", "urgent"),
                "evidence": flag.get("evidence") or [],
                "activate": _activation_for_condition(condition),
            }
        )

    escalation = red_flags.get("escalation_required")
    if escalation and not alerts:
        alerts.append(
            {
                "type": "escalation",
                "condition": "clinical_escalation",
                "urgency": red_flags.get("time_sensitivity", "urgent"),
                "evidence": [],
                "activate": None,
            }
        )

    consults = routing.get("specialist_consults") or []
    priority = routing.get("priority_within_destination", "standard")
    destination = routing.get("primary_destination")
    if audit_report:
        if not destination:
            destination = extract_destination_from_report(audit_report)
        if priority == "standard":
            report_priority = extract_priority_from_report(audit_report)
            if report_priority:
                priority = report_priority

    nurse_notes = feedback.get("nurse_notes_from_history") or []

    return {
        "mission": build_mission_plan(complete=True),
        "routing_order": {
            "destination": destination,
            "priority": priority,
            "consultations": consults,
            "estimated_time_to_provider": routing.get(
                "estimated_time_to_provider"
            ),
            "rationale": routing.get("rationale"),
        },
        "alerts": alerts,
        "esi": {
            "level": display_esi,
            "model_esi": esi,
            "calibrated": esi_calibrated,
            "confidence": esi_conf,
            "adjusted_confidence": adjusted,
        },
        "human_review": {
            "recommend": recommend_review,
            "reasons": review_reasons,
            "status": "pending",
        },
        "phoenix_insight": {
            "similar_cases": similar,
            "overrides": override_count,
            "match_method": feedback.get("match_method"),
            "data_source": feedback.get("data_source"),
            "historical_insight": feedback.get("historical_insight"),
            "calibrated_esi": feedback.get("calibrated_esi"),
            "calibration_reason": feedback.get("calibration_reason"),
            "nurse_notes": nurse_notes,
        },
        "chief_complaint": parsed.get("chief_complaint"),
    }


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "N/A"
