---
name: phoenix-similarity-matching
description: |
  Decide when Phoenix nurse overrides and notes apply to the current triage
  case. Prevents cross-condition leakage (e.g. chest pain override on alcohol
  intake). Used by phoenix-feedback-loop and REST query_phoenix_feedback.
license: Apache-2.0
metadata:
  author: clinictrace
  version: "1.0"
---

# Phoenix similarity matching

## Purpose

Determine whether a **prior nurse override** or **nurse note** from Phoenix
history should influence **this** triage run.

## Search keywords (current case)

Build keywords in this order:

1. `parsed_symptoms.chief_complaint` — short label from clinical-intake-parser
   (preferred; e.g. `"chest pain"`, `"alcohol-related problems"`)
2. Additional `parsed_symptoms.symptoms` entries
3. If parser output is missing, extract from intake:
   `chief complaint: <label>` from NHAMCS-style text
4. Never use the full intake narrative as the primary keyword

## When an override **applies** (all required)

1. **Similar traces found** via one of:
   - `attribute_chief_complaint` — exact span attribute match
   - `keyword_overlap` — symptom keyword overlap on `clinictrace.triage` spans
   - `annotation_metadata` — override annotation metadata matches keywords
2. **Complaint match** — annotation `metadata.chief_complaint` or
   `metadata.symptom_keywords` is clinically the **same presentation** as
   current keywords (not merely “any recent override”)
3. **Override label** is one of: `under_triage`, `over_triage`, `extraction_failed`
4. **Nurse ESI present** — `metadata.nurse_esi` is set for ESI calibration

## When an override **must NOT apply**

- No similar traces found (`match_method: none`)
- Scanning “recent traces” without complaint match (never calibrate from unrelated cases)
- Prior override chief complaint differs (e.g. `chest pain` vs `alcohol-related problems`)
- Nurse note describes a different workup (e.g. MRI for chest pain) on unrelated chief complaint
- **Cross-protocol mismatch** — presentation families differ (MTS-style flows:
  cardiovascular, trauma_injury, neurological, respiratory, toxicology, etc.)
- **Pathway conflict** — nurse note implies ACS/STEMI, stroke, trauma team, sepsis,
  etc. but the current case is a different protocol family
- **`annotation_metadata` only** — may adjust confidence; do **not** apply ESI
  calibration unless match is span-based (`attribute_chief_complaint` or
  `keyword_overlap`)

Fast path (`feedback_matching.py`) encodes these rules using Manchester Triage
System–style presentation groups and common US ED activation pathway markers.

## ESI calibration output

Only set `esi_calibration_applied: true` when steps above pass. Otherwise:

- Keep model ESI from `severity_score`
- Still adjust confidence if complaint-matched override rate warrants it
- Set `historical_insight` to explain that unrelated overrides were ignored

## Examples

| Current case | Prior override CC | Apply? |
|--------------|-------------------|--------|
| Chest pain, diaphoresis | chest pain → ESI 1 | Yes |
| Alcohol-related problems | chest pain → ESI 1 | **No** |
| Chest pain | chest pain, note: activate cath lab | Yes (note + ESI) |
