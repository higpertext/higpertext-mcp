"""Hook PreToolUse:Read — bloquea lecturas completas de archivos grandes.

v2 (2026-09-25):
- Umbral 100 KB -> 24 KB (~6k tokens): con 100 KB un archivo de 90 KB
  (~22k tokens) entraba entero al contexto sin aviso.
- Las tools sugeridas usan el nombre MCP real (`common-smart-read`, con
  guion): el nombre con guion bajo no existe y costaba un turno fallido.
- Mensaje de una línea: el recuadro decorativo también son tokens.
- Lee `file_path` (la clave real del Read de Claude Code): antes solo
  buscaba filePath/path/file y el guard nunca se disparaba en Claude.
- emit_deny en vez de emit_block: niega esa lectura sin cortar la sesión.
Una lectura con `offset`/`limit` explícitos siempre pasa.
"""

from __future__ import annotations
from .hook_utils import get_project_root
from .hook_io import (
    hook_main,
    read_payload,
    emit_continue,
    emit_deny,
)

import os
from pathlib import Path


def _threshold_bytes() -> int:
    try:
        return int(os.environ.get("HIGPERTEXT_READ_GUARD_BYTES", str(24 * 1024)))
    except ValueError:
        return 24 * 1024


def _extract_path(tool_input: dict) -> str:
    return (
        tool_input.get("file_path")
        or tool_input.get("filePath")
        or tool_input.get("filepath")
        or tool_input.get("path")
        or tool_input.get("file")
        or ""
    )


def _has_range(tool_input: dict) -> bool:
    return any(
        key in tool_input and tool_input.get(key) not in (None, "") for key in ("offset", "limit")
    )


def evaluate_read_guard(tool_input: dict, root: Path) -> str:
    """Devuelve mensaje de bloqueo o cadena vacía si la lectura es segura."""
    raw_path = _extract_path(tool_input)
    if not raw_path or _has_range(tool_input):
        return ""
    path = Path(raw_path)
    if not path.is_absolute():
        path = root / path
    if not path.exists() or not path.is_file():
        return ""
    threshold = _threshold_bytes()
    size = path.stat().st_size
    if size <= threshold:
        return ""
    return (
        f"{raw_path} pesa {size / 1024:.0f} KB (~{size // 4000}k tokens; límite {threshold / 1024:.0f} KB). "
        "Leé un rango (Read con offset/limit) o usá "
        f'mcp__higpertext__common-smart-read(path="{raw_path}", mode="auto") / '
        f'mcp__higpertext__common-code-skeletonizer(path="{raw_path}").'
    )


@hook_main
def main() -> None:
    payload = read_payload()
    message = evaluate_read_guard(payload.get("tool_input", {}), get_project_root())
    if message:
        emit_deny("PreToolUse", message)
        return
    emit_continue()


if __name__ == "__main__":
    main()
