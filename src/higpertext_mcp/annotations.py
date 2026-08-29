"""Hints de seguridad/comportamiento por capability, para `Tool.annotations`.

Estático y curado a mano porque las capability JSON no declaran esta info hoy
— inferirla del texto sería frágil. `discovery.py` ahora expone todas las
capabilities que el perfil activo otorgue (no solo un set fijo curado); toda
capability sin entrada acá recibe el hint más conservador (mutating, no
idempotente) por defecto, así que ampliar estos sets es una mejora de UX, no
un requisito de seguridad.
"""

from __future__ import annotations

from dataclasses import dataclass

READ_ONLY_CAPABILITIES: frozenset[str] = frozenset(
    {
        "common.grep-search",
        "git.diff",
        "git.ls-files",
        "common.smart-read",
        "common.code-skeletonizer",
        "common.knowledge-asker",
        "security.secret-scanner",
    }
)

DESTRUCTIVE_CAPABILITIES: frozenset[str] = frozenset(
    {
        "common.quality-resolver",  # puede reescribir archivos existentes
    }
)


@dataclass(frozen=True)
class ToolHints:
    read_only: bool
    destructive: bool
    idempotent: bool


def hints_for(capability_id: str) -> ToolHints:
    read_only = capability_id in READ_ONLY_CAPABILITIES
    destructive = capability_id in DESTRUCTIVE_CAPABILITIES
    return ToolHints(
        read_only=read_only,
        destructive=destructive if not read_only else False,
        idempotent=read_only,
    )
