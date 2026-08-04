"""Shared runtime configuration for ClinTrace agents."""

import os

# Override via CLINICTRACE_MODEL or GEMINI_MODEL in .env
DEFAULT_MODEL = os.getenv(
    "CLINICTRACE_MODEL",
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
)

# Post-triage LLM judge (optional UI path) — lighter than pipeline model.
EVAL_MODEL = os.getenv(
    "GEMINI_EVAL_MODEL",
    os.getenv("CLINICTRACE_EVAL_MODEL", "gemini-3.5-flash"),
)

PHOENIX_PROJECT = (
    os.getenv("PHOENIX_PROJECT_ID")
    or os.getenv("PHOENIX_PROJECT_NAME", "clinictrace")
)

# Fast path: REST feedback only (no extra LLM + npx MCP round-trip).
FAST_TRIAGE = os.getenv("FAST_TRIAGE", "true").lower() in ("true", "1")

# Demo/hackathon: LLM feedback agent with visible Phoenix MCP tool calls.
PHOENIX_MCP_FEEDBACK = os.getenv("PHOENIX_MCP_FEEDBACK", "false").lower() in (
    "true",
    "1",
)

# Inline skill markdown in prompts (avoids extra load_skill LLM turn per agent).
INLINE_SKILLS = os.getenv("INLINE_SKILLS", "true").lower() in ("true", "1")

# Merge ESI+red-flag into one LLM; use deterministic audit report (saves ~2 calls).
MERGE_TRIAGE_LLM_STEPS = os.getenv(
    "MERGE_TRIAGE_LLM_STEPS", "true"
).lower() in ("true", "1")

# NHAMCS UI: skip post-hoc LLM quality judge (saves ~10–15s per run).
UI_SKIP_QUALITY_EVAL = os.getenv("UI_SKIP_QUALITY_EVAL", "true").lower() in (
    "true",
    "1",
)

# Manual intake form: LLM-as-judge quality banner after triage.
UI_INTAKE_LLM_QUALITY_EVAL = os.getenv(
    "UI_INTAKE_LLM_QUALITY_EVAL", "true"
).lower() in ("true", "1")

# Remote Phoenix MCP on Cloud Run (Streamable HTTP). Preferred for Agent Engine.
_raw_mcp_url = os.getenv("PHOENIX_MCP_URL", "").strip()
PHOENIX_MCP_URL = (
    f"{_raw_mcp_url.rstrip('/')}/mcp"
    if _raw_mcp_url and not _raw_mcp_url.rstrip("/").endswith("/mcp")
    else _raw_mcp_url.rstrip("/")
)
PHOENIX_MCP_SERVICE_KEY = os.getenv("PHOENIX_MCP_SERVICE_KEY", "")

# Local stdio MCP (npx). Skipped when PHOENIX_MCP_URL is set.
_mcp_stdio_allowed = os.getenv("DISABLE_PHOENIX_MCP", "false").lower() not in (
    "true",
    "1",
)
_phoenix_mcp_enrich = os.getenv("PHOENIX_MCP_ENRICH", "false").lower() in (
    "true",
    "1",
)
_want_stdio_mcp = _mcp_stdio_allowed and (
    not FAST_TRIAGE or _phoenix_mcp_enrich or PHOENIX_MCP_FEEDBACK
)

USE_PHOENIX_MCP_REMOTE = bool(PHOENIX_MCP_URL)
USE_PHOENIX_MCP_STDIO = _want_stdio_mcp and not USE_PHOENIX_MCP_REMOTE
USE_PHOENIX_MCP = USE_PHOENIX_MCP_REMOTE or USE_PHOENIX_MCP_STDIO

# Feedback step: deterministic REST on FAST_TRIAGE (MCP probe runs in-code).
# PHOENIX_MCP_FEEDBACK enables MCP instrumentation, not an extra LLM agent.
USE_LLM_FEEDBACK = not FAST_TRIAGE
