#!/usr/bin/env python3
"""Filtro standalone: enmascara secretos y resume outputs largos.

Se invoca como `python3 output_filter.py <archivo>` desde el comando Bash
reescrito por hook_bash_output_rewrite (PreToolUse). Lee el archivo donde
quedó redirigido el stdout/stderr real del comando, aplica máscaras de
secretos y, si sigue siendo largo, lo resume conservando head/tail y las
líneas que matchean el patrón de highlights. Imprime el resultado final a
stdout — eso es lo único que Claude Code captura como output del comando.

Nunca debe fallar en silencio perdiendo el output real: ante cualquier
excepción, cae a volcar el archivo tal cual (mejor mostrar de más que
perder datos).
"""

from __future__ import annotations

import re
import sys

_SECRET_PATTERNS = [
    (
        r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*['\"]?[^\s'\"]{8,}",
        r"\1=********[MASKED]",
    ),
    (r"(?i)bearer\s+[a-z0-9._\-]{20,}", "Bearer ********[MASKED]"),
    (r"sk-[a-zA-Z0-9]{20,}", "sk-********[MASKED]"),
]

# v2 (2026-09-19): el pattern anterior (\bERROR\b etc, anclado a límites de
# palabra) NO matcheaba "AssertionError", "undefined reference", "connection
# refused", "permission denied", "fatal:", etc. — un error real embebido en
# la porción omitida del medio podía desaparecer sin que ninguna señal lo
# marcara. Ahora es case-insensitive y por substring (no \b): prioriza sobre-
# marcar (más líneas en highlights, sin límite de daño — solo ocupan más
# espacio, tope _MAX_HIGHLIGHTS) antes que dejar pasar un error real sin
# flaggear. No es exhaustivo — sigue siendo heurístico — pero cubre mucho
# más terreno que antes.
_HIGHLIGHT_PATTERN = re.compile(
    r"fail|error|panic|traceback|exception|assert|undefined reference"
    r"|cannot |can't |denied|refused|fatal|timeout|unable to|invalid"
    r"|not found|no such file|segfault|core dumped|unhandled|warn|✗|✘",
    re.IGNORECASE,
)
_MAX_LINE_CHARS = 2000
# Threshold subido de 4000 a 10000: truncar es un trade-off (ahorra contexto
# pero arriesga ocultar algo fuera de head/tail/highlights) — reservarlo para
# dumps genuinamente grandes en vez de recortar cualquier output moderado.
_THRESHOLD_CHARS = 10000
_HEAD_LINES = 20
_TAIL_LINES = 40
_MAX_HIGHLIGHTS = 60


def mask(text: str) -> str:
    masked = text
    for pattern, replacement in _SECRET_PATTERNS:
        masked = re.sub(pattern, replacement, masked)
    return masked


def _clip_line(line: str) -> str:
    if len(line) <= _MAX_LINE_CHARS:
        return line
    return line[:_MAX_LINE_CHARS] + f"…[línea truncada, {len(line)} caracteres originales]"


def summarize(text: str) -> str:
    if len(text) <= _THRESHOLD_CHARS:
        return text

    lines = [_clip_line(line) for line in text.splitlines()]
    total_lines = len(lines)

    highlights = [line for line in lines if _HIGHLIGHT_PATTERN.search(line)]
    truncated_highlights = len(highlights) > _MAX_HIGHLIGHTS
    highlights = highlights[:_MAX_HIGHLIGHTS]

    head_n = min(_HEAD_LINES, total_lines)
    tail_n = min(_TAIL_LINES, total_lines - head_n)
    head = lines[:head_n]
    tail = lines[total_lines - tail_n :] if tail_n > 0 else []
    omitted = max(0, total_lines - head_n - tail_n)

    sections: list[str] = [
        f"[HIGPERTEXT OUTPUT GUARD] Output original: {len(text)} caracteres / {total_lines} líneas — resumido para ahorrar contexto. Heurístico, no exhaustivo: un error sin palabras clave reconocidas y fuera de head/tail puede no aparecer.",
        "",
    ]
    if highlights:
        sections.append("── Líneas relevantes (posibles errores/fallos) " + "─" * 10)
        sections.extend(highlights)
        if truncated_highlights:
            sections.append(f"… ({len(highlights)}+ líneas relevantes, se muestran las primeras {_MAX_HIGHLIGHTS})")
        sections.append("")

    sections.append("── Inicio del output " + "─" * 10)
    sections.extend(head)
    if omitted > 0:
        sections.append(f"\n… ({omitted} líneas omitidas de {total_lines} totales) …\n")
    sections.append("── Final del output " + "─" * 10)
    sections.extend(tail)

    return "\n".join(sections)


def main() -> None:
    if len(sys.argv) < 2:
        return
    path = sys.argv[1]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
    except OSError:
        return
    try:
        result = summarize(mask(raw))
    except Exception:  # noqa: BLE001 — nunca perder el output real por un bug del filtro
        result = raw
    sys.stdout.write(result)


if __name__ == "__main__":
    main()
