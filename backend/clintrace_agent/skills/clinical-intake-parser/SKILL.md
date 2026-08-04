---
name: clinical-intake-parser
description: |
  Parse free-text ED nursing intake into structured clinical JSON (chief
  complaint, symptoms, vitals, history). Use when normalizing patient_input
  before severity scoring or red-flag screening.
license: Apache-2.0
metadata:
  author: clinictrace
  version: "1.0"
---

# Clinical intake parser

## When to use

Load this skill when the task is to extract and normalize patient information
from free-text nursing notes into a structured JSON object.

## Input

- `patient_input`: raw nursing intake text (session state).

## Output schema

Produce **only** a JSON object (no markdown fences) with:

| Field | Type | Rules |
|-------|------|--------|
| `chief_complaint` | string | One-sentence primary reason for visit |
| `symptoms` | string[] | Normalized medical terminology |
| `vitals` | object | `heart_rate`, `bp_systolic`, `bp_diastolic`, `temp_f`, `resp_rate`, `spo2`, `pain_scale` — use `null` if unavailable |
| `duration` | string | e.g. `"3 days"`, `"acute onset"` |
| `medical_history` | string[] | Prior conditions mentioned |
| `medications` | string[] | Current meds mentioned |
| `allergies` | string[] | Known allergies mentioned |

## Clinical rules

1. **Precision** — Do not infer symptoms not stated or strongly implied by vitals.
2. **Normalization** — Map colloquial terms to standard terms (e.g. `"racing heart"` → `"tachycardia"`).
3. **No hallucination** — Missing data stays null or empty list; do not fabricate vitals.

## Example output shape

```json
{
  "chief_complaint": "Acute chest pain",
  "symptoms": ["chest pain", "diaphoresis", "nausea"],
  "vitals": {"heart_rate": 110, "bp_systolic": 160, "bp_diastolic": 95, "temp_f": null, "resp_rate": 22, "spo2": 94, "pain_scale": 9},
  "duration": "30 minutes",
  "medical_history": ["hypertension", "type 2 diabetes"],
  "medications": ["metformin", "lisinopril"],
  "allergies": []
}
```
