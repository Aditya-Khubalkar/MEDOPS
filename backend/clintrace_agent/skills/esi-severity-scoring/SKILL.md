---
name: esi-severity-scoring
description: |
  Assign Emergency Severity Index (ESI) level 1–5 with confidence and
  reasoning from structured parsed_symptoms. Use lookup_esi_criteria tool for
  reference thresholds when uncertain.
license: Apache-2.0
metadata:
  author: clinictrace
  version: "1.0"
---

# ESI severity scoring

## When to use

After `parsed_symptoms` exists. Assign ESI using structured patient data only.

## ESI levels (summary)

| Level | Name | Criteria |
|-------|------|----------|
| 1 | Immediate | Life-saving intervention now (arrest, apneic, pulseless, major active hemorrhage) |
| 2 | Emergent | High risk, confused/lethargic, severe pain/distress, or danger-zone vitals (HR>150, RR>30, SpO2<90%, temp>104°F) |
| 3 | Urgent | Stable but likely needs **multiple** resources (labs + imaging + IV + consult) |
| 4 | Less urgent | Stable, **one** resource (single lab, simple imaging, Rx) |
| 5 | Non-urgent | Stable, no resources (exam/Rx refill only) |

Call `lookup_esi_criteria(esi_level)` for full criteria and examples when debating between levels.

## Reasoning order

1. Life threat → ESI-1
2. High risk / danger vitals / severe distress → ESI-2
3. Resource count → ESI-3 vs 4 vs 5

## Output schema

JSON only:

```json
{
  "esi_level": 1,
  "confidence": 0.85,
  "reasoning": "2-3 sentences",
  "vital_flags": ["SpO2 88% < threshold 90%"],
  "resource_estimate": 3
}
```

- `confidence`: float 0.0–1.0 (model certainty in assigned ESI)
- `vital_flags`: vitals that influenced the score
- `resource_estimate`: expected resources (0–5+)
