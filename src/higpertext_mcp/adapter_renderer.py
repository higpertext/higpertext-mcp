"""Renderizadores autónomos de configuración para los asistentes soportados.

No importan ni ejecutan adapters de higpertext-cli. Los datos provienen del
profile server y los hooks se materializan por separado desde su catálogo.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from higpertext_mcp import adapter_catalog
from higpertext_mcp.gen.profile.v1 import profile_pb2

SUPPORTED = adapter_catalog.SUPPORTED


def _rules(profile, caps: list, rules: list) -> str:
    """Instrucciones estables; las capabilities se descubren por MCP, no aquí."""
    name = getattr(profile, "name", profile)
    description = getattr(profile, "description", "")
    system_prompt = getattr(profile, "system_prompt", "")
    profile_rules = []
    for rule in getattr(profile, "rules", []):
        rule_description = getattr(rule, "description", str(rule))
        # These statements belonged to the pre-MCP CLI and would contradict
        # the runtime contract if copied into a target project's instructions.
        stale = (
            "o el cwd del proceso servidor",
            "semantic_graph.json",
            "semantic_graph.md/json",
            "make render-hooks",
        )
        if any(marker in rule_description for marker in stale):
            continue
        profile_rules.append(rule_description)
    lines = [f"# Perfil higpertext: {name}", ""]
    if description:
        lines += [description, ""]
    if system_prompt:
        lines += ["## Mandato del perfil", "", system_prompt, ""]
    lines += ["## Gobernanza efectiva", ""]
    lines += [f"- {rule}" for rule in profile_rules]
    lines += [
        "- La raíz del proyecto se selecciona explícitamente mediante `HIGPERTEXT_PROJECT_ROOT` o los selectores soportados por la operación; no se usa la raíz instalada del motor.",
        "- El grafo semántico se consulta mediante las capabilities MCP `common.graph-query` y `common.graph-rebuild`; Redis es la fuente de verdad y no un JSON/Markdown local.",
        "- Los hooks son controles auxiliares de observación/guardrail; la autorización efectiva pertenece al gateway/controlador.",
    ]
    lines += [f"- [{profile_pb2.Severity.Name(r.severity)}] **{r.id}** — {r.description}" for r in rules]
    if not rules and not profile_rules:
        lines.append("- No hay reglas de gobernanza activas para este perfil.")
    lines += [
        "", "## Descubrimiento y permisos", "",
        "- El servidor MCP es la fuente de verdad de capabilities disponibles y permisos efectivos.",
        "- Antes de elegir una capability, consulta las tools MCP disponibles en esta sesión.",
        "- Invoca sólo tools expuestas por el MCP; no infieras capabilities desde este archivo.",
        "- El servidor aplica el perfil activo y rechaza operaciones no autorizadas.", "",
    ]
    return "\n".join(lines)


def _write(path: Path, content: str, written: list[str], root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    written.append(str(path.relative_to(root)))


def _ensure_project_mcp(root: Path, written: list[str]) -> None:
    """Registra higpertext en la configuración MCP común del proyecto.

    La configuración compartida permite que el MCP quede disponible para
    cualquier asistente aunque el adapter renderizado haya sido otro.
    Conserva servidores existentes y sólo agrega higpertext si falta.
    """
    path = root / ".mcp.json"
    if path.exists():
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path} no contiene JSON válido: {exc}") from exc
        if not isinstance(config, dict):
            raise ValueError(f"{path} debe contener un objeto JSON")
    else:
        config = {}

    servers = config.get("mcpServers")
    if servers is None:
        servers = {}
        config["mcpServers"] = servers
    if not isinstance(servers, dict):
        raise ValueError(f"{path}: 'mcpServers' debe ser un objeto")
    if "higpertext" in servers:
        return

    servers["higpertext"] = {
        "type": "http",
        "url": os.environ.get("HIGPERTEXT_MCP_URL", "http://127.0.0.1:8790/mcp/"),
    }
    _write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n", written, root)


def render(root: Path, assistants: list[str], profile, caps: list, rules: list) -> dict:
    specs = adapter_catalog.specs_for(assistants)
    selected = [spec.id for spec in specs]
    profile_name = getattr(profile, "name", profile)
    content = _rules(profile, caps, rules)
    written: list[str] = []
    _ensure_project_mcp(root, written)
    for assistant in selected:
        if assistant == "codex":
            _write(root / "AGENTS.md", content, written, root)
            _write(root / ".agents" / "mcp_config.json", json.dumps({"mcpServers": {"higpertext": {"type": "http", "url": "http://127.0.0.1:8790/mcp/"}}}, indent=2) + "\n", written, root)
        elif assistant == "claude":
            _write(root / ".claude" / "rules" / f"{profile_name}.md", content, written, root)
            _write(root / "CLAUDE.md", f"# {profile_name}\n\nVer `.claude/rules/{profile_name}.md`.\n", written, root)
        elif assistant == "gemini":
            _write(root / "GEMINI.md", content, written, root)
        elif assistant == "copilot":
            _write(root / ".github" / "copilot-instructions.md", content, written, root)
        elif assistant == "antigravity":
            _write(root / "AGENTS.md", content, written, root)
            _write(root / ".agents" / "settings.json", json.dumps({"mcp": "higpertext", "profile": profile_name}, indent=2) + "\n", written, root)
        elif assistant == "opencode":
            # AGENTS.md is the active project instruction file in OpenCode v2.
            _write(root / "AGENTS.md", content, written, root)
            _write(root / "opencode.json", json.dumps({"mcp": {"higpertext": {"type": "remote", "url": "http://127.0.0.1:8790/mcp/"}}}, indent=2) + "\n", written, root)
    return {"assistants": selected, "files": written, "capabilities": len(caps), "rules": len(rules)}
