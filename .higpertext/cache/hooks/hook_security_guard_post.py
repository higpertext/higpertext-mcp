"""Hook común de seguridad para PreToolUse y PostToolUse.

Fix 2026-09-19 (v2): se retira la rama de enmascarado en PostToolUse.
Verificado contra la documentación oficial de Claude Code
(https://code.claude.com/docs/en/hooks.md) y GitHub issue #3983: un hook
PostToolUse NO tiene forma de reemplazar el tool_response/tool output que
ve el modelo — el schema real solo admite `additionalContext`,
`systemMessage` y `terminalSequence`. Ni `replacementOutput` ni
`updatedToolOutput` (probados ambos, en ese orden, en incidentes previos)
existen en el spec ni tienen efecto — confirmado empíricamente leyendo un
archivo con secretos de prueba vía Read: el output llegó sin enmascarar
con los dos campos.

Esto es una limitación de arquitectura, no un bug de esta hook: no hay
forma soportada hoy de enmascarar un secreto embebido en el contenido de
un archivo no marcado como sensible (Read/Grep/etc.) después de que la
tool ya corrió. Lo que SÍ funciona y sigue vigente:
  - Bash: `hook_bash_output_rewrite` (PreToolUse) reescribe el comando
    ANTES de ejecutarlo, así que el filtro corre dentro del propio
    comando — no depende de reemplazar un tool_response.
  - Read/Write/Edit sobre rutas conocidas como sensibles (.env, id_rsa,
    etc.): `evaluate_path_guard` en PreToolUse, más abajo en este mismo
    archivo, BLOQUEA el acceso antes de que exista output que enmascarar.

`mask_tool_output` sigue existiendo en `_rules/security_rules.py` por
compatibilidad, pero deliberadamente no se llama desde acá.
"""

from __future__ import annotations

from .hook_io import (
    hook_main,
    read_payload,
    read_tool_command,
    emit_block,
    emit_context,
    emit_continue,
)
from .hook_utils import get_project_root
from ._rules.security_rules import evaluate_command_guard, evaluate_path_guard


def _tool_name(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("tool") or "")


@hook_main
def main() -> None:
    payload = read_payload()
    event = payload.get("event", "PreToolUse")
    tool_name = _tool_name(payload)
    root = get_project_root()

    if event == "PreToolUse":
        if tool_name in {"Bash", "PowerShell"}:
            result = evaluate_command_guard(read_tool_command(payload), root)
        else:
            result = evaluate_path_guard(tool_name, payload.get("tool_input", {}))
        if result:
            if result.severity == "warn":
                emit_context("PreToolUse", result.message)
                return
            emit_block("PreToolUse", result.message)
            return
        emit_continue()
        return

    # PostToolUse: no-op deliberado, ver docstring del módulo.
    emit_continue()


if __name__ == "__main__":
    main()
