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
from higpertext_mcp import adapter_catalog

# Multiple assistants can share a directory (codex/antigravity both use
# .agents/skills) — rendering is deduplicated by directory, not by assistant.
_SKILLS_DIR = {
    name: spec.skills_dir
    for name, spec in adapter_catalog.ADAPTERS.items()
    if spec.supports_skills
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
    # Cada adapter declara su directorio nativo en adapter_catalog. Los
    # adapters que comparten una ruta se deduplican más abajo.
    selected = list(dict.fromkeys(assistants)) or list(adapter_catalog.SUPPORTED)
    invalid = sorted(set(selected) - set(adapter_catalog.SUPPORTED))
    if invalid:
        raise ValueError(f"skill adapters not supported: {', '.join(invalid)}")
    selected = [a for a in selected if a in _SKILLS_DIR]

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
