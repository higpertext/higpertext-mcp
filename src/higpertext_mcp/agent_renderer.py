"""Render subagentes por asistente desde AgentService — la DB es la fuente de
verdad, nunca un archivo hecho a mano.

Mismo shape de scoping/prune que skill_renderer.py, con diferencias propias:
- Los agents materializan como archivos PLANOS `<id>.<ext>` (no `<id>/SKILL.md`
  como Skill, que usa un directorio por skill).
- El contenido se SINTETIZA desde campos estructurados, y el formato de esa
  síntesis es DISTINTO por asistente (YAML frontmatter+Markdown para Claude
  Code, TOML para Codex CLI) — mismo criterio que hook_renderer._plan(),
  que también transforma un mismo HookDefinition a un formato nativo por
  asistente en vez de asumir uno solo. `_ASSISTANTS` es el punto único que
  declara, por asistente, directorio + extensión + función de síntesis.

Como un archivo materializado puede haber sido editado a mano, todo archivo
que este renderer toca (escribe o poda) debe llevar `_MARKER_TEXT` en un
comentario (sintaxis de comentario propia de cada formato); un archivo
preexistente sin la marca nunca se sobreescribe ni se borra — se reporta en
`skipped_unmanaged`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from higpertext_mcp import adapter_catalog, discovery, profile_client

_MARKER_TEXT = "managed_by: higpertext-mcp"


def _visible(agent: dict, project_id: str, profile: str) -> bool:
    profiles = agent.get("profiles") or []
    agent_project_id = agent.get("project_id") or ""
    if not profiles and not agent_project_id:
        return True  # global
    if agent_project_id and agent_project_id == project_id:
        return True
    return bool(profile) and profile in profiles


def _for_adapter(agent: dict, assistant: str) -> dict | None:
    """Return an adapter-specific agent or None when a global agent is incompatible.

    An explicit target is configuration intent, so an incompatible model there
    is an error. A global agent is intentionally broad; it is simply omitted
    from adapters for which its base model has no compatible override.
    """
    overrides = agent.get("model_overrides") or {}
    model = overrides.get(assistant, agent.get("model", ""))
    if adapter_catalog.get(assistant).supports_model(model):
        return {**agent, "model": model}
    if agent.get("assistants"):
        raise ValueError(
            f"agent '{agent['id']}' usa el modelo '{model}' incompatible con el adaptador '{assistant}'; "
            f"configure model_overrides.{assistant} o quite ese destino"
        )
    return None


# ── Claude Code: .claude/agents/<id>.md — YAML frontmatter + cuerpo markdown ──

_CLAUDE_FRONTMATTER_ORDER = ("permission_mode", "skills", "memory", "background", "color", "effort")
_CLAUDE_FRONTMATTER_KEY = {
    "permission_mode": "permissionMode",
    "skills": "skills",
    "memory": "memory",
    "background": "background",
    "color": "color",
    "effort": "effort",
}


def _render_claude(agent: dict) -> str:
    lines = ["---", f"name: {agent['name']}", f"description: {agent['description']}"]
    if agent.get("tools"):
        lines.append(f"tools: {', '.join(agent['tools'])}")
    if agent.get("model"):
        lines.append(f"model: {agent['model']}")
    for key in _CLAUDE_FRONTMATTER_ORDER:
        value = agent.get(key)
        if value in (None, "", []):
            continue
        rendered = ", ".join(value) if isinstance(value, list) else value
        lines.append(f"{_CLAUDE_FRONTMATTER_KEY[key]}: {rendered}")
    lines.append("---")
    body = (agent.get("prompt") or "").rstrip("\n")
    return "\n".join(lines) + "\n\n" + body + "\n\n" + f"<!-- {_MARKER_TEXT} -->" + "\n"


def _render_copilot(agent: dict) -> str:
    """Render the repository-level Copilot custom-agent format.

    Copilot agents use Markdown with YAML frontmatter.  Only fields documented
    by Copilot are emitted; Claude-specific options are intentionally omitted.
    """
    lines = ["---", f"name: {agent['name']}", f"description: {agent['description']}"]
    if agent.get("tools"):
        lines.append(f"tools: [{', '.join(agent['tools'])}]")
    if agent.get("model"):
        lines.append(f"model: {agent['model']}")
    lines.append("---")
    body = (agent.get("prompt") or "").rstrip("\n")
    return "\n".join(lines) + "\n\n" + body + "\n\n" + f"<!-- {_MARKER_TEXT} -->" + "\n"


def _render_opencode(agent: dict) -> str:
    """Render an OpenCode project agent.

    OpenCode uses Markdown agents with YAML frontmatter.  The common agent
    contract maps cleanly to its required description and a subagent mode;
    provider-specific fields are intentionally not copied across adapters.
    """
    lines = [
        "---",
        f"description: {agent['description']}",
        "mode: subagent",
    ]
    if agent.get("model"):
        lines.append(f"model: {agent['model']}")
    lines.append("---")
    body = (agent.get("prompt") or "").rstrip("\n")
    return "\n".join(lines) + "\n\n" + body + "\n\n" + f"<!-- {_MARKER_TEXT} -->" + "\n"


# ── Codex CLI: .codex/agents/<id>.toml ────────────────────────────────────
#
# Campos soportados por Codex (name, description, developer_instructions,
# model, model_reasoning_effort): mapeo directo. `tools` (allowlist),
# `permission_mode`, `skills` y `color`/`memory` de Claude Code NO tienen
# equivalente en el schema de Codex (lo más cercano, `sandbox_mode`, es un
# enum distinto sin correspondencia 1:1 con `permissionMode`) — se omiten a
# propósito en vez de forzar un mapeo aproximado que rompería en silencio.

def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _toml_multiline_string(value: str) -> str:
    body = value.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    return f'"""\n{body}\n"""'


def _render_codex(agent: dict) -> str:
    lines = [
        f"name = {_toml_string(agent['name'])}",
        f"description = {_toml_string(agent['description'])}",
        f"developer_instructions = {_toml_multiline_string(agent.get('prompt') or '')}",
    ]
    if agent.get("model"):
        lines.append(f"model = {_toml_string(agent['model'])}")
    if agent.get("effort"):
        lines.append(f"model_reasoning_effort = {_toml_string(agent['effort'])}")
    lines.append("")
    lines.append(f"# {_MARKER_TEXT}")
    return "\n".join(lines) + "\n"


# Declaración única por asistente: directorio destino, extensión de archivo,
# función de síntesis. Agregar un asistente nuevo es sumar una entrada acá.
_FORMAT_RENDERERS: dict[str, Callable[[dict], str]] = {
    "claude-markdown": _render_claude,
    "copilot-markdown": _render_copilot,
    "codex-toml": _render_codex,
    "opencode-markdown": _render_opencode,
}
_ASSISTANTS: dict[str, dict[str, object]] = {
    spec.id: {
        "dir": spec.agents_dir,
        "ext": spec.agents_extension,
        "render": _FORMAT_RENDERERS[spec.agents_format],
    }
    for spec in adapter_catalog.ADAPTERS.values()
    if spec.supports_agents
}


def _is_managed(path: Path) -> bool:
    return path.exists() and _MARKER_TEXT in path.read_text(encoding="utf-8")


def _prune(dir_path: Path, ext: str, want_ids: set[str]) -> list[str]:
    if not dir_path.exists():
        return []
    removed = []
    for entry in dir_path.iterdir():
        if not entry.is_file() or entry.suffix != ext:
            continue
        agent_id = entry.stem
        if agent_id in want_ids:
            continue
        if _is_managed(entry):
            entry.unlink()
            removed.append(agent_id)
    return removed


async def render(root: Path, profile: str, assistants: list[str]) -> dict[str, dict[str, list[str]]]:
    selected = list(dict.fromkeys(assistants)) or list(adapter_catalog.SUPPORTED)
    invalid = sorted(set(selected) - set(adapter_catalog.SUPPORTED))
    if invalid:
        raise ValueError(f"agent adapters not supported: {', '.join(invalid)}")
    selected = [a for a in selected if a in _ASSISTANTS]

    project = await profile_client.resolve_project(str(discovery.canonical_project_path(root)))
    project_id = project.get("id", "")

    agents = await profile_client.list_agents()
    visible = [a for a in agents if _visible(a, project_id, profile)]
    planned: dict[str, list[dict]] = {}
    for assistant in sorted(selected):
        target_agents: list[dict] = []
        for agent in visible:
            targets = agent.get("assistants") or []
            if targets and assistant not in targets:
                continue
            adapted = _for_adapter(agent, assistant)
            if adapted is not None:
                target_agents.append(adapted)
        planned[assistant] = target_agents

    result: dict[str, dict[str, list[str]]] = {}
    for assistant in sorted(selected):
        cfg = _ASSISTANTS[assistant]
        rel_dir: str = cfg["dir"]  # type: ignore[assignment]
        ext: str = cfg["ext"]  # type: ignore[assignment]
        render_one: Callable[[dict], str] = cfg["render"]  # type: ignore[assignment]

        dir_path = root / rel_dir
        dir_path.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        skipped: list[str] = []
        for agent in planned[assistant]:
            path = dir_path / f"{agent['id']}{ext}"
            if path.exists() and not _is_managed(path):
                skipped.append(str(path.relative_to(root)))
                continue
            path.write_text(render_one(agent), encoding="utf-8")
            written.append(str(path.relative_to(root)))
        want_ids = {agent["id"] for agent in planned[assistant]}
        removed = _prune(dir_path, ext, want_ids)
        result[rel_dir] = {"written": written, "pruned": removed, "skipped_unmanaged": skipped}
    return result
