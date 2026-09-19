#!/usr/bin/env python3
"""Filtro standalone: enmascara secretos y resume outputs largos.

Se invoca como `python3 output_filter.py <archivo>` desde el comando Bash
reescrito por hook_bash_output_rewrite (PreToolUse). Lee el archivo donde
quedó redirigido el stdout/stderr real del comando, aplica máscaras de
secretos y, si sigue siendo largo, lo resume conservando head/tail y las
líneas con FAIL/ERROR/panic. Imprime el resultado final a stdout — eso es
lo único que Claude Code captura como output del comando.

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

_HIGHLIGHT_PATTERN = re.compile(r"\b(FAIL|ERROR|Error|panic|Traceback|✗|✘|--- FAIL)\b")
_MAX_LINE_CHARS = 2000
_THRESHOLD_CHARS = 4000
_HEAD_LINES = 15
_TAIL_LINES = 30
_MAX_HIGHLIGHTS = 40


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
        f"[HIGPERTEXT OUTPUT GUARD] Output original: {len(text)} caracteres / {total_lines} líneas — resumido para ahorrar contexto.",
        "",
    ]
    if highlights:
        sections.append("── Líneas relevantes (FAIL/ERROR/panic) " + "─" * 10)
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
