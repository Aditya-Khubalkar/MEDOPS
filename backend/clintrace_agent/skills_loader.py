"""Load ClinTrace ADK skills (agentskills.io / progressive disclosure).

Each pipeline sub-agent gets a dedicated skill so L2 instructions load on demand
via load_skill instead of bloating every LLM call. See clintrace_agent/skills/*/SKILL.md.
"""

from __future__ import annotations

from pathlib import Path

from google.adk.agents.llm_agent import ToolUnion
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset

_SKILLS_ROOT = Path(__file__).parent / "skills"


def _skill_dir(name: str) -> Path:
    path = _SKILLS_ROOT / name
    if not path.is_dir():
        raise FileNotFoundError(f"Skill directory not found: {path}")
    return path


def load_clinictrace_skill(name: str):
    """Load one file-based skill by directory name under clintrace_agent/skills/."""
    return load_skill_from_dir(_skill_dir(name))


def skill_toolset_for(
    skill_name: str,
    *,
    additional_tools: list[ToolUnion] | None = None,
) -> SkillToolset:
    """SkillToolset with list_skills / load_skill / load_skill_resource tools."""
    return SkillToolset(
        skills=[load_clinictrace_skill(skill_name)],
        additional_tools=additional_tools,
    )


def read_skill_body(skill_name: str) -> str:
    """Return SKILL.md body without YAML frontmatter."""
    raw = (_skill_dir(skill_name) / "SKILL.md").read_text(encoding="utf-8")
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            return raw[end + 3 :].strip()
    return raw.strip()


def agent_instruction_with_skill(skill_name: str, preamble: str) -> str:
    """Build agent instruction with inlined skill (no load_skill round-trip)."""
    return f"{preamble.strip()}\n\n{read_skill_body(skill_name)}"


def agent_instruction_with_skills(
    skill_names: list[str],
    preamble: str,
) -> str:
    """Inline multiple skills into one agent instruction."""
    parts = [preamble.strip()]
    for name in skill_names:
        parts.append(read_skill_body(name))
    return "\n\n".join(parts)
