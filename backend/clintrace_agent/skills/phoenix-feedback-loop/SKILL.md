---
name: phoenix-feedback-loop
description: |
  Recalibrate triage confidence using Phoenix trace history (REST +
  optional MCP). Use on slow-path feedback_agent with query_phoenix_feedback
  and Phoenix MCP list-traces / get-span-annotations.
license: Apache-2.0
metadata:
  author: clinictrace
  version: "1.1"
---

# Phoenix feedback loop

## When to use

After routing, before audit report. Inputs in session state:

- `parsed_symptoms`, `severity_score`, `red_flags`, `routing`

## Similarity matching (required reading)

Follow **phoenix-similarity-matching** rules before applying any nurse ESI
or nurse note from history. Never calibrate from unrelated chief complaints.

## Steps (strict order)

1. Call `query_phoenix_feedback` with:
   - `parsed_symptoms` (JSON string from clinical-intake-parser)
   - `current_confidence` from `severity_score.confidence`
   - `current_esi` from `severity_score.esi_level` when available
   - `patient_input` only as fallback when parsed symptoms are empty

   The tool uses Phoenix span attributes (`clinictrace.chief_complaint`,
   `clinictrace.symptom_keywords`) and annotation metadata for
   **complaint-matched** overrides only.

2. If `similar_cases_found == 0`, do **not** apply ESI from recent unrelated
   traces. Optionally use Phoenix MCP for trace inspection only when
   `PHOENIX_MCP_FEEDBACK` is enabled — still require complaint match.

3. Output **only** the JSON from step 1 (or complaint-filtered adjustment).

## Override labels (Phoenix annotations)

Treat as overrides: `under_triage`, `over_triage`, `extraction_failed`.

## Confidence adjustment (already in tool output)

- Override rate > 30% on **matched** similar cases → −0.20 confidence
- Override rate > 15% → −0.10 confidence
- `recommend_human_review` when adjusted confidence < 0.7
