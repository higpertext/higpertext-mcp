"""Formato de mensaje AI-legible compartido por las reglas de hooks."""

from __future__ import annotations

import re

def render_box(title: str, lines: list[str]) -> str:
    """Título + líneas, sin marco.

    v2 (2026-09-25): el recuadro de 60 columnas (╔───…╚───) y el relleno de
    alineación son tokens que el modelo paga en cada block/warn sin aportar
    información. Se conserva la firma para no tocar a los llamadores.
    """
    body = [re.sub(r"\s{2,}:", ":", line.strip()) for line in lines if line.strip()]
    return "\n".join([f"[{title}]", *body])
