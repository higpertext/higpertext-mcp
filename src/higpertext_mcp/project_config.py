"""Materializa la configuración mínima de un proyecto que usa higpertext-mcp.

El servidor no presupone que el proyecto destino ya tenga ``.higpertext``.
Esta función permite que la tool de bootstrap lo prepare sin destruir
configuración que el usuario ya tuviera.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _read_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path} no contiene JSON válido: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} debe contener un objeto JSON")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def create_project_configuration(root: Path, profile: str) -> dict[str, list[str]]:
    """Crea configuración no invasiva y devuelve archivos creados/omitidos.

    Nunca reemplaza una selección de perfil o un servidor MCP ya existentes:
    hacerlo podría dejar al proyecto apuntando a otro entorno sin que el
    usuario lo hubiera pedido. Sí conserva y amplía objetos JSON existentes.
    """
    if not profile or not profile.strip():
        raise ValueError("'profile' es obligatorio")
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"la raíz de proyecto no existe o no es directorio: {root}")

    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []

    environment_path = root / ".higpertext" / "config" / "environment.json"
    environment_existed = environment_path.exists()
    environment = _read_object(environment_path)
    assert environment is not None
    current_profile = environment.get("active_profile")
    if current_profile:
        skipped.append(str(environment_path.relative_to(root)))
    else:
        environment["active_profile"] = profile.strip()
        _write_json(environment_path, environment)
        (created if not environment_existed else updated).append(
            str(environment_path.relative_to(root))
        )

    external_path = root / ".higpertext" / "config" / "mcp_external.json"
    if not external_path.exists():
        _write_json(external_path, {"servers": []})
        created.append(str(external_path.relative_to(root)))
    else:
        # Validarlo evita que el bootstrap parezca exitoso con un JSON roto;
        # completar la clave faltante conserva los demás ajustes del usuario.
        external = _read_object(external_path)
        assert external is not None
        if "servers" not in external:
            external["servers"] = []
            _write_json(external_path, external)
            updated.append(str(external_path.relative_to(root)))
        elif not isinstance(external["servers"], list):
            raise ValueError(f"{external_path}: 'servers' debe ser una lista")
        else:
            skipped.append(str(external_path.relative_to(root)))

    mcp_path = root / ".mcp.json"
    mcp_existed = mcp_path.exists()
    mcp_config = _read_object(mcp_path)
    assert mcp_config is not None
    servers = mcp_config.get("mcpServers")
    if servers is None:
        servers = {}
        mcp_config["mcpServers"] = servers
    if not isinstance(servers, dict):
        raise ValueError(f"{mcp_path}: 'mcpServers' debe ser un objeto")
    if "higpertext" in servers:
        skipped.append(str(mcp_path.relative_to(root)))
    else:
        # El despliegue soportado es Streamable HTTP en Docker. Esto evita
        # requerir una CLI o un virtualenv del MCP en cada proyecto cliente.
        servers["higpertext"] = {
            "type": "http",
            "url": os.environ.get("HIGPERTEXT_MCP_URL", "http://127.0.0.1:8790/mcp/"),
        }
        _write_json(mcp_path, mcp_config)
        (created if not mcp_existed else updated).append(str(mcp_path.relative_to(root)))

    return {"created": created, "updated": updated, "skipped": skipped}


def write_codex_rules(root: Path, profile: str, capabilities: list, rules: list) -> str:
    """Inserta una sección administrada por higpertext en el AGENTS.md de Codex."""
    path = root / "AGENTS.md"
    start, end = "<!-- higpertext:rules:start -->", "<!-- higpertext:rules:end -->"
    lines = [start, "", f"## Perfil higpertext: {profile}", "", "### Capabilities permitidas", ""]
    lines.extend(f"- `{item.id}` — {item.description}" for item in capabilities)
    lines.extend(["", "### Reglas de gobernanza", ""])
    lines.extend(f"- [{item.severity}] **{item.id}** — {item.description}" for item in rules)
    if not rules:
        lines.append("- No hay reglas de gobernanza activas para este perfil.")
    lines.extend(["", end, ""])
    section = "\n".join(lines)
    original = path.read_text(encoding="utf-8") if path.exists() else "# Instrucciones del proyecto\n"
    if start in original and end in original:
        prefix, remainder = original.split(start, 1)
        _old, suffix = remainder.split(end, 1)
        content = prefix.rstrip() + "\n\n" + section + suffix.lstrip()
    else:
        content = original.rstrip() + "\n\n" + section
    path.write_text(content, encoding="utf-8")
    return str(path.relative_to(root))
