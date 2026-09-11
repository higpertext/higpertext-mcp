"""Render SKILL.md files from SkillService — the DB is the source of truth,
never a hardcoded template baked into this module (that was the old, now
removed, `adapter_renderer.WORKFLOWS` behavior).

Same shape as `hook_renderer.render`, called from the same
`higpertext-render-adapters` handler in server.py. Unlike hooks, skill
`content` is not transformed per assistant: it already carries its full YAML
front matter, so materializing it is a byte-for-byte copy into every
destination directory — mirrors `cmd/render-skills` in
higpertext-server-profile (the Go counterpart of this exact tool), which
established the scoping rules this module also follows: a skill is visible
if it's global (no `profiles` and no `project_id`, e.g. any `common.*`
skill), if its `project_id` matches this project's, or if `profile` is in
its `profiles` list.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from higpertext_mcp import discovery, profile_client

# Multiple assistants can share a directory (codex/antigravity both use
# .agents/skills) — rendering is deduplicated by directory, not by assistant.
_SKILLS_DIR = {
    "claude": ".claude/skills",
    "gemini": ".gemini/skills",
    "codex": ".agents/skills",
    "antigravity": ".agents/skills",
}


def _visible(skill: dict, project_id: str, profile: str) -> bool:
    profiles = skill.get("profiles") or []
    skill_project_id = skill.get("project_id") or ""
    if not profiles and not skill_project_id:
        return True  # global — típicamente "common.*"
    if skill_project_id and skill_project_id == project_id:
        return True
    return bool(profile) and profile in profiles


def _prune(dir_path: Path, want_ids: set[str]) -> list[str]:
    if not dir_path.exists():
        return []
    removed = []
    for entry in dir_path.iterdir():
        if not entry.is_dir() or entry.name in want_ids:
            continue
        if (entry / "SKILL.md").exists():
            shutil.rmtree(entry)
            removed.append(entry.name)
    return removed


async def render(root: Path, profile: str, assistants: list[str]) -> dict[str, dict[str, list[str]]]:
    # A diferencia de hook_renderer, un asistente sin concepto de skills (hoy
    # copilot/opencode) no es un error — simplemente no recibe nada acá.
    selected = [a for a in dict.fromkeys(assistants) if a in _SKILLS_DIR] or list(_SKILLS_DIR)

    project = await profile_client.resolve_project(str(discovery.canonical_project_path(root)))
    project_id = project.get("id", "")

    skills = await profile_client.list_skills(enabled_only=True)
    visible = [s for s in skills if _visible(s, project_id, profile)]
    want_ids = {s["id"] for s in visible}

    result: dict[str, dict[str, list[str]]] = {}
    for rel_dir in sorted({_SKILLS_DIR[a] for a in selected}):
        dir_path = root / rel_dir
        dir_path.mkdir(parents=True, exist_ok=True)
        written = []
        for skill in visible:
            skill_dir = dir_path / skill["id"]
            skill_dir.mkdir(parents=True, exist_ok=True)
            path = skill_dir / "SKILL.md"
            path.write_text(skill["content"], encoding="utf-8")
            written.append(str(path.relative_to(root)))
        removed = _prune(dir_path, want_ids)
        result[rel_dir] = {"written": written, "pruned": removed}
    return result
