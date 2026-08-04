"""Shared JSON parsing helpers for ADK session state values."""

from __future__ import annotations

import json
from typing import Any


def parse_json_blob(value: Any) -> dict[str, Any]:
    """Parse a session-state value into a dict.

    Args:
        value: Dict, JSON string, or other session state blob.

    Returns:
        Parsed dict, or empty dict when value is missing or invalid.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
