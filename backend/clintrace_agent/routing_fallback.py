"""Deterministic ED routing when the router LLM omits or invalidates routing JSON."""

from __future__ import annotations

from typing import Any

from clintrace_agent.json_utils import parse_json_blob


def _flag_conditions(red_flags: dict[str, Any]) -> list[str]:
    conditions: list[str] = []
    for flag in red_flags.get("red_flags_detected") or []:
        if isinstance(flag, dict) and flag.get("condition"):
            conditions.append(str(flag["condition"]).lower())
    return conditions


def _has_condition(conditions: list[str], *needles: str) -> bool:
    for cond in conditions:
        for needle in needles:
            if needle in cond:
                return True
    return False


def _routing_is_incomplete(routing: dict[str, Any]) -> bool:
    dest = routing.get("primary_destination")
    if not dest or str(dest).upper() in ("N/A", "NONE", "NULL", ""):
        return True
    if not routing.get("rationale"):
        return True
    return False


def infer_routing_from_clinical_state(
    *,
    parsed_symptoms: Any,
    severity_score: Any,
    red_flags: Any,
) -> dict[str, Any]:
    """Infer minimum safe routing from ESI and red-flag screening."""
    severity = parse_json_blob(severity_score)
    flags = parse_json_blob(red_flags)
    parsed = parse_json_blob(parsed_symptoms)
    if not severity and not flags and not parsed:
        return {}
    conditions = _flag_conditions(flags)
    esi = severity.get("esi_level")
    time_sens = str(flags.get("time_sensitivity") or "").lower()

    if _has_condition(conditions, "stroke"):
        return {
            "primary_destination": "STROKE_TEAM",
            "specialist_consults": ["Neurology"],
            "rationale": (
                "Acute stroke presentation within treatment window — "
                "stroke team activation, urgent CT, and neurology consult."
            ),
            "priority_within_destination": "immediate",
            "estimated_time_to_provider": "< 5 min",
        }

    if _has_condition(conditions, "stemi", "acs", "myocardial", "coronary"):
        return {
            "primary_destination": "CARDIAC_CATH",
            "specialist_consults": ["Cardiology"],
            "rationale": (
                "Suspected acute coronary syndrome — cardiac monitoring "
                "and cardiology evaluation."
            ),
            "priority_within_destination": "immediate",
            "estimated_time_to_provider": "< 5 min",
        }

    if _has_condition(conditions, "sepsis"):
        return {
            "primary_destination": "ED_ACUTE",
            "specialist_consults": ["Infectious Disease"],
            "rationale": "Sepsis concern — acute ED bed and sepsis bundle.",
            "priority_within_destination": "immediate",
            "estimated_time_to_provider": "< 10 min",
        }

    if _has_condition(conditions, "anaphylaxis"):
        return {
            "primary_destination": "RESUSCITATION",
            "specialist_consults": [],
            "rationale": "Anaphylaxis — resuscitation bay and immediate treatment.",
            "priority_within_destination": "immediate",
            "estimated_time_to_provider": "< 5 min",
        }

    if _has_condition(conditions, "pe", "pulmonary embolism", "embolism"):
        return {
            "primary_destination": "ED_ACUTE",
            "specialist_consults": ["Pulmonology"],
            "rationale": "Possible pulmonary embolism — urgent workup.",
            "priority_within_destination": "immediate",
            "estimated_time_to_provider": "< 10 min",
        }

    if flags.get("escalation_required") or time_sens == "minutes":
        return {
            "primary_destination": "ED_ACUTE",
            "specialist_consults": [],
            "rationale": (
                "Time-critical presentation — acute ED evaluation "
                "without delay."
            ),
            "priority_within_destination": "immediate",
            "estimated_time_to_provider": "< 10 min",
        }

    if esi == 1:
        return {
            "primary_destination": "RESUSCITATION",
            "specialist_consults": [],
            "rationale": "ESI 1 — immediate resuscitation.",
            "priority_within_destination": "immediate",
            "estimated_time_to_provider": "< 5 min",
        }

    if esi == 2:
        return {
            "primary_destination": "ED_ACUTE",
            "specialist_consults": [],
            "rationale": "ESI 2 — high-risk; acute ED bed and rapid provider.",
            "priority_within_destination": "immediate",
            "estimated_time_to_provider": "< 10 min",
        }

    if esi in (4, 5):
        return {
            "primary_destination": "FAST_TRACK",
            "specialist_consults": [],
            "rationale": "Lower acuity — fast-track evaluation.",
            "priority_within_destination": "queue",
            "estimated_time_to_provider": "30-60 min",
        }

    return {
        "primary_destination": "ED_STANDARD",
        "specialist_consults": [],
        "rationale": "Stable presentation — standard ED workflow.",
        "priority_within_destination": "next",
        "estimated_time_to_provider": "15-30 min",
    }


def merge_routing(
    llm_routing: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    """Prefer valid LLM fields; fill gaps from fallback."""
    merged = dict(fallback)
    for key, value in llm_routing.items():
        if value is None:
            continue
        if isinstance(value, str) and value.strip().upper() in (
            "",
            "N/A",
            "NONE",
            "NULL",
        ):
            continue
        if key == "specialist_consults" and value == []:
            continue
        merged[key] = value
    return merged


def complete_routing_from_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return routing dict with clinically safe defaults applied."""
    llm = parse_json_blob(state.get("routing"))
    inferred = infer_routing_from_clinical_state(
        parsed_symptoms=state.get("parsed_symptoms"),
        severity_score=state.get("severity_score"),
        red_flags=state.get("red_flags"),
    )
    if _routing_is_incomplete(llm):
        return merge_routing(llm, inferred)
    # Fill individual missing fields even when destination exists
    merged = merge_routing(llm, inferred)
    if not llm.get("specialist_consults") and inferred.get("specialist_consults"):
        merged["specialist_consults"] = inferred["specialist_consults"]
    if (
        llm.get("priority_within_destination") in (None, "standard", "N/A")
        and inferred.get("priority_within_destination") == "immediate"
    ):
        merged["priority_within_destination"] = "immediate"
    return merged
