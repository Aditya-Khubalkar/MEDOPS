"""Deterministic CLINTRACE audit report from workflow session state."""

from __future__ import annotations

import json
import re
from typing import Any

from clintrace_agent.json_utils import parse_json_blob
from clintrace_agent.routing_fallback import complete_routing_from_state


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2)


def _pct(confidence: Any) -> str:
    try:
        return f"{float(confidence) * 100:.0f}%"
    except (TypeError, ValueError):
        return "N/A"


def is_valid_audit_report(text: str) -> bool:
    """True if text looks like a completed audit report, not a prompt for data."""
    if not text or not text.strip():
        return False
    upper = text.upper()
    if "CLINTRACE TRIAGE AUDIT REPORT" in upper:
        return True
    if re.search(r"ESI\s*Level:\s*[1-5]", text, re.IGNORECASE):
        return True
    # Reject model asking for pipeline inputs
    if "please provide" in text.lower() and "parsed_symptoms" in text.lower():
        return False
    if "need the following information" in text.lower():
        return False
    return False


def build_audit_report_from_state(state: dict[str, Any]) -> str:
    """Build the audit report purely from session state (no LLM)."""
    parsed = parse_json_blob(state.get("parsed_symptoms"))
    severity = parse_json_blob(state.get("severity_score"))
    red_flags = parse_json_blob(state.get("red_flags"))
    routing = complete_routing_from_state(state)
    feedback = parse_json_blob(state.get("feedback_analysis"))

    esi = severity.get("esi_level", "N/A")
    esi_conf = severity.get("confidence", 0.0)
    adjusted = feedback.get("adjusted_confidence", esi_conf)
    display_esi = feedback.get("calibrated_esi") or esi
    esi_calibrated = bool(feedback.get("esi_calibration_applied"))
    recommend_review = feedback.get("recommend_human_review", False)
    if esi in (1, 2):
        recommend_review = True
    try:
        if float(esi_conf) < 0.7:
            recommend_review = True
    except (TypeError, ValueError):
        pass

    symptoms = parsed.get("symptoms") or []
    vitals = parsed.get("vitals") or {}
    vitals_parts = [
        f"{k}: {v}" for k, v in vitals.items() if v is not None
    ]
    flags = red_flags.get("red_flags_detected") or []
    flag_status = "FLAGS DETECTED" if flags else "CLEAR"
    flag_lines = []
    for flag in flags:
        if isinstance(flag, dict):
            flag_lines.append(
                f"  - {flag.get('condition', '?')}: "
                f"{', '.join(flag.get('evidence') or [])} "
                f"({flag.get('urgency', '')})"
            )

    consults = routing.get("specialist_consults") or []
    consult_str = ", ".join(consults) if consults else "None required"
    recommendation = (
        "HUMAN REVIEW RECOMMENDED" if recommend_review else "PROCEED"
    )

    lines = [
        "═══════════════════════════════════════════════════",
        "CLINTRACE TRIAGE AUDIT REPORT",
        "═══════════════════════════════════════════════════",
        "",
        "PATIENT PRESENTATION",
        f"• Chief Complaint: {parsed.get('chief_complaint', 'N/A')}",
        f"• Symptoms: {', '.join(symptoms) if symptoms else 'N/A'}",
        f"• Vitals: {', '.join(vitals_parts) if vitals_parts else 'N/A'}",
        f"• Duration: {parsed.get('duration', 'N/A')}",
        f"• Relevant History: {', '.join(parsed.get('medical_history') or []) or 'N/A'}",
        "",
        "SEVERITY ASSESSMENT",
        f"• ESI Level: {display_esi} (Confidence: {_pct(esi_conf)})",
    ]
    if esi_calibrated and display_esi != esi:
        lines.append(
            f"• Phoenix calibration: nurse corrected similar case to ESI "
            f"{display_esi} (model scored ESI {esi})"
        )
    if feedback.get("calibration_reason"):
        lines.append(f"• Calibration: {feedback.get('calibration_reason')}")
    lines.extend(
        [
        f"• Reasoning: {severity.get('reasoning', 'N/A')}",
        f"• Vital Sign Flags: {', '.join(severity.get('vital_flags') or []) or 'None'}",
        "",
        "RED FLAG SCREENING",
        f"• Status: {flag_status}",
    ])
    if flag_lines:
        lines.extend(flag_lines)
    lines.extend(
        [
            f"• Time Sensitivity: {red_flags.get('time_sensitivity', 'routine')}",
            "",
            "ROUTING DECISION",
            f"• Destination: {routing.get('primary_destination', 'N/A')}",
            f"• Priority: {routing.get('priority_within_destination', 'N/A')}",
            f"• Specialist Consults: {consult_str}",
            f"• Estimated Time to Provider: "
            f"{routing.get('estimated_time_to_provider', 'N/A')}",
            f"• Rationale: {routing.get('rationale', 'N/A')}",
            "",
            "DECISION CONFIDENCE & AUDIT TRAIL",
            f"• ESI Confidence: {_pct(esi_conf)}",
            f"• Adjusted Confidence: {_pct(adjusted)}",
            f"• Historical Insight: {feedback.get('historical_insight', 'N/A')}",
            f"• Adjustment Reason: {feedback.get('adjustment_reason', 'N/A')}",
            f"• Similar Cases / Overrides: "
            f"{feedback.get('similar_cases_found', 0)} / "
            f"{feedback.get('override_count', 0)}",
            f"• Recommendation: {recommendation}",
            "• Trace ID: full reasoning trace logged to Arize Phoenix",
            "",
            "═══════════════════════════════════════════════════",
        ]
    )
    return "\n".join(lines)
