---
name: ed-specialist-routing
description: |
  Route ED patients to destination and specialist consults using
  parsed_symptoms, severity_score, and red_flags from prior pipeline steps.
license: Apache-2.0
metadata:
  author: clinictrace
  version: "1.0"
---

# ED specialist routing

## When to use

After clinical join: `parsed_symptoms`, `severity_score`, and `red_flags` are available.

## Destinations (primary_destination)

| Code | Use when |
|------|----------|
| RESUSCITATION | ESI-1, active life threat |
| TRAUMA_BAY | Significant MOI, unstable trauma |
| CARDIAC_CATH | STEMI / ACS with ST changes |
| STROKE_TEAM | Acute stroke in intervention window |
| ICU_DIRECT | Critical, not immediately surgical |
| ED_ACUTE | ESI-2/3, needs physician now, not resus |
| ED_STANDARD | ESI-3 stable, needs workup |
| FAST_TRACK | ESI-4/5 minor complaints |
| BEHAVIORAL_HEALTH | Psych emergency, SI/HI |
| OB_TRIAGE | Pregnancy-related |
| PEDIATRIC | Age < 18 |

## Specialist consults (optional list)

Cardiology, Neurology, Surgery (General/Ortho/Neuro), Pulmonology, GI,
Nephrology, Infectious Disease, Psychiatry, OB/GYN, Pediatrics, Toxicology,
Pain Management.

## Output schema

JSON only:

```json
{
  "primary_destination": "CARDIAC_CATH",
  "specialist_consults": ["Cardiology"],
  "rationale": "2-3 sentences",
  "priority_within_destination": "immediate",
  "estimated_time_to_provider": "< 5 min"
}
```

- `priority_within_destination`: `"immediate"` | `"next"` | `"queue"`

Resolve conflicts: red-flag escalation overrides lower-acuity routing when clinically indicated.
