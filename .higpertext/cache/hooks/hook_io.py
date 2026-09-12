"""Protocolo I/O centralizado para hook tasks de higpertext.

Single source of truth para:
- Leer el payload de stdin (read_payload, read_tool_command)
- Emitir respuestas JSON al runtime del asistente
  (emit_continue, emit_context, emit_block, emit_deny)
- Decorador @hook_main que envuelve cualquier main() con manejo de errores
"""

from __future__ import annotations
from typing import Callable
import functools
import json
import sys


def read_payload() -> dict:
    """Lee y parsea el JSON de stdin. Retorna {} ante cualquier error."""
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        return {}


def read_tool_command(payload: dict) -> str:
    """Extrae el comando de tool_input, con fallback a CommandLine (PowerShell)."""
    tool_input = payload.get("tool_input", {})
    return tool_input.get("command") or tool_input.get("CommandLine") or ""


def emit_continue(error: str = "") -> None:
    """Emite continue:True, opcionalmente con campo error."""
    out: dict = {"continue": True}
    if error:
        out["error"] = error
    print(json.dumps(out))


def emit_context(event: str, text: str) -> None:
    """Emite continue:True con additionalContext (hook informativo)."""
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": text,
                },
            }
        )
    )


def emit_block(event: str, text: str) -> None:
    """Emite continue:False deteniendo TODO el bucle agéntico (hard stop de sesión).

    Reservar para incidentes reales (ej. comando destructivo a mitad de tarea).
    Para negar solo la llamada puntual a una tool sin cortar la sesión, usar
    emit_deny — es lo que corresponde a la gran mayoría de las reglas de
    gobernanza (redirigir a una capacidad, pedir confirmación, etc.).
    """
    print(
        json.dumps(
            {
                "continue": False,
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": text,
                },
            }
        )
    )


def emit_deny(event: str, reason: str) -> None:
    """Niega la llamada puntual a la tool (PreToolUse) sin cortar la sesión.

    El modelo recibe `reason` como feedback y puede reintentar con otro
    enfoque en el mismo turno — a diferencia de emit_block, que detiene el
    bucle agéntico completo apenas termina el batch de tool calls actual.
    """
    print(
        json.dumps(
            {
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                },
            }
        )
    )


def hook_main(fn: Callable) -> Callable:
    """Decorador que envuelve main() capturando excepciones → emit_continue+error."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            emit_continue(str(exc))

    return wrapper
