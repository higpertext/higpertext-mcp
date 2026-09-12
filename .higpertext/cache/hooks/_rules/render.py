"""Formato de bloque AI-legible compartido por las reglas de hooks."""

from __future__ import annotations

_BOX_WIDTH = 60


def render_box(title: str, lines: list[str]) -> str:
    header_fill = "─" * max(0, _BOX_WIDTH - len(title) - 1)
    header = f"╔─ {title} {header_fill}"
    footer = "╚" + "─" * (_BOX_WIDTH + 2)
    return "\n".join([header, *lines, footer])
