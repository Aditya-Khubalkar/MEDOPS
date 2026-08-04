"""Shared rules for Phoenix nurse-override similarity (REST + skill parity).

Implements clintrace_agent/skills/phoenix-similarity-matching/SKILL.md for the fast
deterministic feedback path.

Presentation groups follow real ED triage protocol buckets:
- Manchester Triage System (MTS) presenting-complaint flow families
- Common US ED activation pathways (ACS/STEMI, stroke, sepsis, trauma, etc.)

We do not enumerate every diagnosis — only protocol-level presentation groups
and high-signal pathway markers used for nurse activation.
"""

from __future__ import annotations

from typing import Any

from clintrace_agent.trace_context import (
    keyword_overlap_score,
    normalize_chief_complaint,
)

OVERRIDE_LABELS = frozenset(
    {
        "under_triage",
        "over_triage",
        "extraction_failed",
    }
)

# ESI calibration only from span-based similarity (not metadata scans).
CALIBRATION_MATCH_METHODS = frozenset(
    {
        "attribute_chief_complaint",
        "keyword_overlap",
    }
)

MIN_COMPLAINT_SIMILARITY = 0.34
ANNOTATION_METADATA_MIN_SIMILARITY = 0.55

# MTS-style presenting-complaint flow families (not exhaustive diagnoses).
_PRESENTATION_FAMILIES: dict[str, tuple[str, ...]] = {
    "cardiovascular": (
        "chest pain",
        "crushing chest",
        "substernal",
        "radiating to left arm",
        "palpitation",
        "cardiac",
        "acs",
        "stemi",
        "myocardial",
        "diaphoresis",
    ),
    "respiratory": (
        "shortness of breath",
        "difficulty breathing",
        "dyspnea",
        "wheez",
        "asthma",
        "copd",
        "respiratory distress",
        "cough",
        "hemoptysis",
    ),
    "neurological": (
        "stroke",
        "seizure",
        "headache",
        "altered mental",
        "confusion",
        "syncope",
        "weakness",
        "facial droop",
        "slurred speech",
        "loss of consciousness",
        "loc",
    ),
    "gastrointestinal": (
        "abdominal pain",
        "vomiting",
        "diarrhea",
        "gi bleed",
        "melena",
        "hematemesis",
        "nausea",
    ),
    "trauma_injury": (
        "head injury",
        "neck injury",
        "face injury",
        "unspecified injury of the head",
        "laceration",
        "fracture",
        "fall",
        "mvc",
        "motor vehicle",
        "blunt trauma",
        "penetrating",
        "wound",
    ),
    "musculoskeletal": (
        "back pain",
        "limb pain",
        "joint pain",
        "sprain",
        "dislocation",
    ),
    "mental_health": (
        "suicidal",
        "self-harm",
        "psychiatric",
        "agitation",
        "behavioral",
        "anxiety",
        "depression",
    ),
    "toxicology": (
        "alcohol",
        "intoxication",
        "overdose",
        "poisoning",
        "withdrawal",
        "substance",
    ),
    "genitourinary": (
        "flank pain",
        "kidney stone",
        "renal colic",
        "urinary",
        "dysuria",
        "hematuria",
        "testicular",
    ),
    "obstetric_gynaecological": (
        "pregnancy",
        "pregnant",
        "vaginal bleeding",
        "pelvic pain",
        "obstetric",
        "gynaecological",
        "gynecological",
    ),
    "ent_ophthalmic": (
        "sore throat",
        "ear pain",
        "eye pain",
        "vision",
        "dental",
        "tooth",
    ),
    "infectious": (
        "fever",
        "sepsis",
        "cellulitis",
        "abscess",
        "infection",
    ),
    "allergic": (
        "anaphylaxis",
        "allergic reaction",
        "angioedema",
        "hives",
        "urticaria",
    ),
}

# ED activation pathway markers → protocol family (small, high-signal list).
_PATHWAY_MARKERS: dict[str, tuple[str, ...]] = {
    "cardiovascular": (
        "stemi",
        "nstemi",
        "acs pathway",
        "cath lab",
        "cardiac cath",
        "activate cath",
        "troponin",
        "heparin",
        "nitro drip",
    ),
    "neurological": (
        "code stroke",
        "stroke team",
        "stroke alert",
        "tpa",
        "thrombectomy",
        "nihss",
    ),
    "trauma_injury": (
        "trauma team",
        "trauma alert",
        "ct head",
        "head ct",
        "c-spine",
        "pan scan",
        "neurosurgery",
    ),
    "respiratory": (
        "pe pathway",
        "ctpa",
        "pulmonary embolism",
        "bipap",
    ),
    "infectious": (
        "sepsis bundle",
        "code sepsis",
        "sepsis alert",
        "broad spectrum",
    ),
    "allergic": (
        "epinephrine",
        "adrenaline",
        "anaphylaxis kit",
    ),
}


def calibration_allowed(match_method: str) -> bool:
    """ESI calibration requires symptom-aware matching, not blind trace scans."""
    base = match_method.split("_low_n")[0]
    return base in CALIBRATION_MATCH_METHODS


def _min_similarity(match_method: str | None) -> float:
    if match_method and match_method.split("_low_n")[0] == "annotation_metadata":
        return ANNOTATION_METADATA_MIN_SIMILARITY
    return MIN_COMPLAINT_SIMILARITY


def _combined_text(*parts: Any) -> str:
    return " ".join(str(part) for part in parts if part).lower()


def detect_presentation_families(text: str) -> frozenset[str]:
    """Map free text to MTS-style ED presentation protocol families."""
    if not text:
        return frozenset({"general"})
    lowered = text.lower()
    found: set[str] = set()
    for family, phrases in _PRESENTATION_FAMILIES.items():
        if any(phrase in lowered for phrase in phrases):
            found.add(family)
    return frozenset(found) if found else frozenset({"general"})


def _families_from_keywords(keywords: list[str]) -> frozenset[str]:
    return detect_presentation_families(_combined_text(*keywords))


def _families_from_meta(meta: dict[str, Any]) -> frozenset[str]:
    ann_keywords = meta.get("symptom_keywords") or []
    if isinstance(ann_keywords, str):
        ann_keywords = [k.strip() for k in ann_keywords.split(",")]
    chief = meta.get("chief_complaint") or meta.get("chiefComplaint")
    note = meta.get("nurse_note") or meta.get("note")
    return detect_presentation_families(
        _combined_text(chief, *ann_keywords, note),
    )


def _presentation_families_compatible(
    keywords: list[str],
    meta: dict[str, Any],
) -> bool:
    """Reject cross-protocol matches (e.g. cardiovascular override on trauma)."""
    kw_families = _families_from_keywords(keywords) - {"general"}
    meta_families = _families_from_meta(meta) - {"general"}
    if not kw_families or not meta_families:
        return True
    return bool(kw_families & meta_families)


def _pathway_families_in_note(note: str) -> frozenset[str]:
    if not note:
        return frozenset()
    lowered = note.lower()
    found: set[str] = set()
    for family, markers in _PATHWAY_MARKERS.items():
        if any(marker in lowered for marker in markers):
            found.add(family)
    return frozenset(found)


def _pathway_note_conflicts(keywords: list[str], meta: dict[str, Any]) -> bool:
    """Reject when nurse note implies a different ED activation pathway."""
    note = _combined_text(meta.get("nurse_note"), meta.get("note"))
    if not note:
        return False
    note_families = _pathway_families_in_note(note)
    if not note_families:
        return False
    kw_families = _families_from_keywords(keywords) - {"general"}
    if not kw_families:
        return False
    return not bool(note_families & kw_families)


def complaint_similarity(keywords: list[str], meta: dict[str, Any]) -> float:
    """Score how closely annotation complaint metadata matches this case."""
    if not keywords:
        return 0.0
    normalized = [normalize_chief_complaint(k) for k in keywords if k]
    if not normalized:
        return 0.0
    primary = normalized[0]
    best = 0.0
    chief = meta.get("chief_complaint") or meta.get("chiefComplaint")
    if chief:
        chief_norm = normalize_chief_complaint(str(chief))
        if chief_norm == primary:
            return 1.0
        if chief_norm in primary or primary in chief_norm:
            best = max(best, 0.5)
        for kn in normalized:
            if len(kn) >= 4 and kn in chief_norm:
                best = max(best, 0.7)
            if len(chief_norm) >= 4 and chief_norm in kn:
                best = max(best, 0.5)
    ann_keywords = meta.get("symptom_keywords") or []
    if isinstance(ann_keywords, str):
        ann_keywords = [k.strip() for k in ann_keywords.split(",")]
    if ann_keywords:
        joined = ",".join(
            normalize_chief_complaint(str(k)) for k in ann_keywords if k
        )
        best = max(best, keyword_overlap_score(normalized, joined))
        for kn in normalized:
            if len(kn) >= 4 and kn in joined:
                best = max(best, 0.7)
    return best


def annotation_matches_case(
    meta: dict[str, Any],
    keywords: list[str],
    *,
    min_similarity: float | None = None,
    match_method: str | None = None,
) -> bool:
    """True when override metadata is for a clinically similar presentation."""
    threshold = (
        min_similarity if min_similarity is not None else _min_similarity(match_method)
    )
    if complaint_similarity(keywords, meta) < threshold:
        return False
    if not _presentation_families_compatible(keywords, meta):
        return False
    if _pathway_note_conflicts(keywords, meta):
        return False
    return True
