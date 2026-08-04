"""Shared agent data types."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TriageResult:
    """Container for triage pipeline output and observability metadata."""

    audit_report: str
    trace_id: str
    actions: dict[str, Any] = field(default_factory=dict)
    detail_audit_report: str | None = None
    session_id: str = ""
    run_started_at: str = ""
