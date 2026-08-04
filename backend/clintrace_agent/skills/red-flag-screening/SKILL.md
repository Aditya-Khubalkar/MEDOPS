---
name: red-flag-screening
description: |
  Screen parsed_symptoms for time-critical conditions (sepsis, stroke, STEMI,
  anaphylaxis, PE, trauma) independent of ESI. Use lookup_red_flag_criteria
  for condition-specific thresholds.
license: Apache-2.0
metadata:
  author: clinictrace
  version: "1.0"
---

# Red-flag screening

## When to use

Parallel with severity scoring — analyze `parsed_symptoms` only; do **not** wait for ESI.

## Categories to screen

### Sepsis (qSOFA-style)

- Altered mental status; RR ≥ 22; SBP ≤ 100
- Temp > 101.3°F or < 96.8°F; HR > 90 with suspected infection

### Stroke (BE-FAST)

Balance, Eyes, Face, Arms, Speech, Time of onset

### Cardiac

Chest pain with radiation/diaphoresis/SOB; new arrhythmia signs; troponin-suggestive pattern

### Anaphylaxis

Rapid onset after exposure + respiratory distress or hypotension

### Trauma

Mechanism suggesting internal injury; altered consciousness post-injury

### Other time-critical

DKA/HHS, pulmonary embolism, ectopic pregnancy indicators

Use `lookup_red_flag_criteria(condition)` with: `sepsis`, `stroke`, `stemi`, `anaphylaxis`, `pe`.

## Output schema

JSON only:

```json
{
  "red_flags_detected": [
    {
      "condition": "Acute coronary syndrome",
      "evidence": ["crushing chest pain", "diaphoresis"],
      "urgency": "immediate"
    }
  ],
  "escalation_required": true,
  "escalation_reason": "STEMI pathway",
  "time_sensitivity": "minutes"
}
```

- `urgency`: `"immediate"` | `"urgent"` | `"monitor"`
- `time_sensitivity`: `"minutes"` | `"hours"` | `"routine"`
- If none: empty `red_flags_detected`, `escalation_required: false`, `escalation_reason: null`
