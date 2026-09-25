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


def _front_matter(content: str) -> tuple[str, str] | None:
    if not content.startswith("---\n"):
        return None
    end = content.find("\n---\n", 4)
    if end < 0:
        return None
    return content[4:end], content[end + 5 :]


def _yaml_scalar(block: str, key: str) -> str:
    prefix = f"{key}:"
    for line in block.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip().strip("\"'")
    return ""


def _permission_allows(block: str, key: str) -> bool:
    """Lee `permission.<key>: allow|deny` del front matter de una tarea."""
    capture = False
    for line in block.splitlines():
        if line.startswith("permission:"):
            capture = True
            continue
        if capture and line and not line.startswith((" ", "\t")):
            break
        stripped = line.strip()
        if capture and stripped.startswith(f"{key}:"):
            return stripped.split(":", 1)[1].strip() == "allow"
    return False


def _when_to_use(body: str, description: str) -> str:
    capture = False
    items: list[str] = []
    for line in body.splitlines():
        heading = line.strip().lower()
        if heading in {"# when to use", "## when to use"}:
            capture = True
            continue
        if capture and line.startswith("#"):
            break
        if capture and line.strip().startswith("- "):
            items.append(line.strip()[2:].strip())
    return "; ".join(items) if items else description


def project_for_grok(content: str) -> str:
    """Proyecta una tarea global `mode: primary` al contrato nativo de Grok.

    Esas tareas no pertenecen a un solo proyecto: son el flujo de la
    herramienta (spec, plan, build, review, compact). El front matter de
    origen usa campos de otro asistente (`mode`, `temperature`, `permission`);
    Grok decide cuándo invocarlas con `name`, `description` y `when-to-use`.
    El cuerpo no se reescribe. El resto de skills se copia igual.
    """
    parts = _front_matter(content)
    if parts is None:
        return content
    front, body = parts
    if _yaml_scalar(front, "mode") != "primary":
        return content
    name = _yaml_scalar(front, "name").replace(".", "-").replace("_", "-")
    description = _yaml_scalar(front, "description")
    tools = ["read_file", "grep", "list_dir"]
    if _permission_allows(front, "edit"):
        tools.append("search_replace")
    if _permission_allows(front, "bash"):
        tools.append("run_terminal_command")
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        f"when-to-use: {_when_to_use(body, description)}",
        "user-invocable: true",
        "allowed-tools: " + ", ".join(tools),
        "---",
        "",
    ]
    return "\n".join(lines) + body.lstrip("\n")


def _materialize(rel_dir: str, content: str) -> str:
    if rel_dir == ".grok/skills":
        return project_for_grok(content)
    return content


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
            path.write_text(_materialize(rel_dir, skill["content"]), encoding="utf-8")
            written.append(str(path.relative_to(root)))
        removed = _prune(dir_path, want_ids)
        result[rel_dir] = {"written": written, "pruned": removed}
    return result
