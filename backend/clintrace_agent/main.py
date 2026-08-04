"""ClinTrace CLI entry point.

Runs a single triage through the pipeline with tracing enabled.
"""

import asyncio
import sys

# Instrumentation MUST be imported first
from . import instrumentation  # noqa: F401

from .runtime import run_triage


def main():
    """Main entry point for CLI usage."""
    if len(sys.argv) > 1:
        patient_input = " ".join(sys.argv[1:])
    else:
        patient_input = (
            "45-year-old male presenting with crushing chest pain radiating "
            "to left arm for 30 minutes. Diaphoretic, nauseated. "
            "BP 160/95, HR 110, RR 22, SpO2 94% on room air. "
            "History of hypertension and type 2 diabetes. "
            "Current meds: metformin, lisinopril. No known allergies. "
            "Pain scale 9/10."
        )
        print(f"No input provided. Using demo case:\n{patient_input}\n")

    print("=" * 60)
    print("CLINTRACE: Running triage pipeline...")
    print("=" * 60)

    result = asyncio.run(run_triage(patient_input))
    print(result.audit_report)
    print(f"\n[Trace ID: {result.trace_id}]")


if __name__ == "__main__":
    main()
