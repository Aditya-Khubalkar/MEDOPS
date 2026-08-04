"""Feedback query tool for the self-improvement loop.

Provides a structured interface for querying Phoenix trace history to
find past triage decisions with similar profiles.
"""

from google.adk.tools import FunctionTool


def format_trace_query(
    symptom_keywords: list[str],
    esi_level: int | None = None,
    limit: int = 20,
) -> str:
    """Format a natural-language query for the Phoenix MCP trace search.

    The FeedbackAgent uses Phoenix MCP tools directly, but this helper
    structures the query intent for the agent to use when calling list-traces
    or get-spans.

    Args:
        symptom_keywords: Key symptoms to search for in past traces.
        esi_level: Optional ESI level to filter by.
        limit: Maximum number of traces to retrieve.

    Returns:
        A formatted query description for the agent to use with Phoenix MCP.
    """
    query_parts = [
        f"Find the last {limit} triage traces from project 'clinictrace'",
        f"where symptoms included: {', '.join(symptom_keywords)}",
    ]
    if esi_level is not None:
        query_parts.append(f"and ESI level was {esi_level}")
    query_parts.append(
        "Include span annotations showing human overrides or eval scores."
    )
    return " ".join(query_parts)


def compute_confidence_adjustment(
    override_count: int,
    total_similar: int,
    current_confidence: float,
) -> dict:
    """Compute how much to adjust confidence based on historical overrides.

    If the agent has been overridden frequently on similar cases, it should
    lower its confidence and recommend human review.

    Args:
        override_count: Number of times humans overrode the agent on similar cases.
        total_similar: Total similar cases found.
        current_confidence: The agent's current confidence score (0.0-1.0).

    Returns:
        Dictionary with adjusted_confidence, adjustment_reason, and
        recommend_human_review flag.
    """
    if total_similar == 0:
        return {
            "adjusted_confidence": current_confidence,
            "adjustment_reason": "No similar historical cases found.",
            "recommend_human_review": current_confidence < 0.7,
        }

    override_rate = override_count / total_similar

    if override_rate > 0.3:
        penalty = 0.2
        reason = (
            f"High override rate ({override_rate:.0%}) on {total_similar} "
            f"similar cases. Reducing confidence significantly."
        )
    elif override_rate > 0.15:
        penalty = 0.1
        reason = (
            f"Moderate override rate ({override_rate:.0%}) on {total_similar} "
            f"similar cases. Reducing confidence."
        )
    else:
        penalty = 0.0
        reason = (
            f"Low override rate ({override_rate:.0%}) on {total_similar} "
            f"similar cases. Confidence maintained."
        )

    adjusted = max(0.0, current_confidence - penalty)
    return {
        "adjusted_confidence": round(adjusted, 2),
        "adjustment_reason": reason,
        "recommend_human_review": adjusted < 0.7,
    }


trace_query_tool = FunctionTool(func=format_trace_query)
confidence_adjustment_tool = FunctionTool(func=compute_confidence_adjustment)
