---
name: triage-audit-report
description: |
  Generate the CLINTRACE TRIAGE AUDIT REPORT plain-text document from all
  pipeline state keys including Phoenix feedback_analysis.
license: Apache-2.0
metadata:
  author: clinictrace
  version: "1.0"
---

# Triage audit report

## When to use

Final pipeline step. Synthesize all prior outputs into a medical-record-suitable report.

## Inputs

The user message includes JSON/text for `parsed_symptoms`, `severity_score`,
`red_flags`, `routing`, and `feedback_analysis`. **Never ask for more data.**
If a field is empty, write N/A in that section and still produce the full report.

## Report format (plain text, NOT JSON)

```
═══════════════════════════════════════════════════
CLINTRACE TRIAGE AUDIT REPORT
═══════════════════════════════════════════════════

PATIENT PRESENTATION
• Chief Complaint: ...
• Symptoms: ...
• Vitals: ... (flag abnormal values)
• Duration: ...
• Relevant History: ...

SEVERITY ASSESSMENT
• ESI Level: ... (Confidence: ...%)
• Reasoning: ...
• Vital Sign Flags: ...

RED FLAG SCREENING
• Status: CLEAR | FLAGS DETECTED
• [each flag: condition, evidence, urgency]
• Time Sensitivity: ...

ROUTING DECISION
• Destination: ...
• Priority: ...
• Specialist Consults: ...
• Estimated Time to Provider: ...
• Rationale: ...

DECISION CONFIDENCE & AUDIT TRAIL
• ESI Confidence: ...% (from severity_score)
• Adjusted Confidence: ...% (from feedback_analysis)
• Historical Insight: ...
• Adjustment Reason: ...
• Similar Cases / Overrides: ...
• Recommendation: PROCEED | HUMAN REVIEW RECOMMENDED
• Trace ID: note full reasoning trace is in Arize Phoenix
═══════════════════════════════════════════════════
```

## Human review rules

Set **HUMAN REVIEW RECOMMENDED** if any:

- `feedback_analysis.recommend_human_review` is true
- ESI confidence < 0.7
- Conflicting severity vs red flags
- ESI-1 or ESI-2 (always physician confirmation)

Otherwise **PROCEED**.
