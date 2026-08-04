"""Extract structured fields from CLINTRACE audit report text."""

from __future__ import annotations

import re
from typing import Any


def _audit_field(report: str, pattern: str) -> str | None:
    match = re.search(pattern, report, re.IGNORECASE | re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    return value if value and value.upper() != "N/A" else None


def _pct_field(report: str, pattern: str) -> float | None:
    field = _audit_field(report, pattern)
    if not field:
        return None
    try:
        return int(field) / 100.0
    except ValueError:
        return None


def extract_esi_from_report(report: str) -> int | None:
    """Extract ESI level (1-5) from audit report text."""
    field = _audit_field(report, r"•\s*ESI Level:\s*(\d)")
    if field:
        level = int(field)
        return level if 1 <= level <= 5 else None
    patterns = [
        r"ESI\s*Level:\s*(\d)",
        r"esi_level[\"']?\s*:\s*(\d)",
        r"ESI-(\d)",
    ]
    for pattern in patterns:
        match = re.search(pattern, report, re.IGNORECASE)
        if match:
            level = int(match.group(1))
            if 1 <= level <= 5:
                return level
    return None


def extract_confidence_from_report(report: str) -> float | None:
    """Extract model confidence from audit report (0.0-1.0)."""
    field = _audit_field(
        report,
        r"•\s*ESI Level:\s*\d+\s*\(Confidence:\s*(\d+)%\)",
    )
    if field:
        return int(field) / 100.0
    match = re.search(
        r"Confidence:\s*(\d+)%",
        report,
        re.IGNORECASE,
    )
    if match:
        return int(match.group(1)) / 100.0
    return None


def extract_destination_from_report(report: str) -> str | None:
    """Extract routing destination from audit report."""
    return _audit_field(report, r"•\s*Destination:\s*([^\n]+)")


def extract_priority_from_report(report: str) -> str | None:
    """Extract routing priority from audit report."""
    return _audit_field(
        report,
        r"•\s*Priority:\s*([^\n]+)",
    )


def extract_feedback_from_report(report: str) -> dict[str, Any]:
    """Parse Phoenix feedback fields embedded in a deterministic audit report."""
    feedback: dict[str, Any] = {}

    adjusted = _pct_field(report, r"•\s*Adjusted Confidence:\s*(\d+)%")
    if adjusted is not None:
        feedback["adjusted_confidence"] = adjusted

    counts = re.search(
        r"•\s*Similar Cases / Overrides:\s*(\d+)\s*/\s*(\d+)",
        report,
        re.IGNORECASE,
    )
    if counts:
        feedback["similar_cases_found"] = int(counts.group(1))
        feedback["override_count"] = int(counts.group(2))

    insight = _audit_field(report, r"•\s*Historical Insight:\s*([^\n]+)")
    if insight:
        feedback["historical_insight"] = insight

    adjustment = _audit_field(report, r"•\s*Adjustment Reason:\s*([^\n]+)")
    if adjustment:
        feedback["adjustment_reason"] = adjustment

    calibration = _audit_field(report, r"•\s*Calibration:\s*([^\n]+)")
    if calibration:
        feedback["calibration_reason"] = calibration

    cal_line = re.search(
        r"Phoenix calibration:.*?ESI\s*(\d+).*?model scored ESI\s*(\d+)",
        report,
        re.IGNORECASE,
    )
    if cal_line:
        feedback["calibrated_esi"] = int(cal_line.group(1))
        feedback["model_esi"] = int(cal_line.group(2))
        feedback["esi_calibration_applied"] = True
    else:
        model_match = re.search(
            r"model scored ESI\s*(\d+)",
            report,
            re.IGNORECASE,
        )
        display = extract_esi_from_report(report)
        if model_match and display is not None:
            model_esi = int(model_match.group(1))
            if model_esi != display:
                feedback["model_esi"] = model_esi
                feedback["calibrated_esi"] = display
                feedback["esi_calibration_applied"] = True

    if "HUMAN REVIEW RECOMMENDED" in report.upper():
        feedback["recommend_human_review"] = True

    notes_match = re.search(
        r"Prior nurse note\(s\):\s*([^\n]+)",
        report,
        re.IGNORECASE,
    )
    if notes_match:
        feedback["nurse_notes_from_history"] = [
            note.strip()
            for note in notes_match.group(1).split("|")
            if note.strip()
        ]

    method_match = re.search(
        r"via\s+(\S+)\s+\(",
        report,
        re.IGNORECASE,
    )
    if method_match:
        feedback["match_method"] = method_match.group(1)

    if feedback:
        feedback["data_source"] = "audit_report_parse"
    return feedback
