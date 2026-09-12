"""Adaptador de gobernanza — valores por defecto para las reglas de hooks.

Antes intentaba cargar contratos de dominio (security_guardrails.json,
deployment_gates.json, etc.) vía el ContractLoader del kernel de
higpertext-cli. Ese kernel ya no es una dependencia del sistema de hooks, así
que estas funciones devuelven directamente los defaults — si en el futuro se
quiere gobernanza configurable por proyecto, este es el punto de extensión.
"""

from __future__ import annotations
from pathlib import Path

DEFAULT_HARD_BLOCKS = [
    (r"\bsudo\b", "sudo no está permitido en este entorno por política de seguridad"),
    (
        r"\bgit\s+push\b",
        "git push es una acción exclusiva del usuario"
        " — el agente no puede publicar cambios al remoto",
    ),
]
DEFAULT_FUNC_LIMIT = 30
DEFAULT_CLASS_LIMIT = 200


def get_bash_blocks(root: Path) -> list[tuple[str, str]]:
    """Bloqueos hard de bash."""
    return DEFAULT_HARD_BLOCKS


def get_deployment_blocks(root: Path) -> list[tuple[str, str, str]]:
    """Retorna (pattern, reason, severity) de deployment gates. Sin defaults hoy."""
    return []


def get_code_limits(root: Path) -> tuple[int, int]:
    """Retorna (max_function_lines, max_class_lines)."""
    return (DEFAULT_FUNC_LIMIT, DEFAULT_CLASS_LIMIT)
