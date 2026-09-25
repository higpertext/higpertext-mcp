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

import os
import re
import sys
import tempfile
import time

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
# v3.1 (2026-09-25): umbral 20000, medido. Replay sobre 62 sesiones reales
# (~3960 salidas de Bash): con 6000 se recortaban 76 salidas, ahorro 9.7 %, y
# en el 34 % de los recortes el agente usaba después identificadores de la
# parte omitida (context miss); con 10000/15000 el miss rate era 47/33 %. Las
# salidas grandes suelen ser lecturas deliberadas (cat/sed -n) que el agente
# SÍ necesita. Con 20000: 0 misses, 1.6 % de ahorro — queda como red de
# seguridad para volcados gigantes, no como fuente de ahorro. El output
# completo se guarda en disco (ver _persist) igual.
_THRESHOLD_CHARS = 20000
_HEAD_LINES = 20
_TAIL_LINES = 40
_MAX_HIGHLIGHTS = 40
_OUTPUT_DIR = os.path.join(tempfile.gettempdir(), "higpertext-outputs")
_KEEP_OUTPUTS = 30


def mask(text: str) -> str:
    masked = text
    for pattern, replacement in _SECRET_PATTERNS:
        masked = re.sub(pattern, replacement, masked)
    return masked


def _clip_line(line: str) -> str:
    if len(line) <= _MAX_LINE_CHARS:
        return line
    return line[:_MAX_LINE_CHARS] + f"…[línea truncada, {len(line)} caracteres originales]"


def _persist(text: str) -> str:
    """Guarda el output completo (ya enmascarado) y devuelve su ruta, o "".

    Rota a los últimos _KEEP_OUTPUTS archivos para no crecer sin límite.
    """
    try:
        os.makedirs(_OUTPUT_DIR, mode=0o700, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix=time.strftime("%H%M%S-"), suffix=".log", dir=_OUTPUT_DIR)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        files = sorted(
            (os.path.join(_OUTPUT_DIR, name) for name in os.listdir(_OUTPUT_DIR)),
            key=os.path.getmtime,
        )
        for old in files[:-_KEEP_OUTPUTS]:
            os.remove(old)
        return path
    except OSError:
        return ""


def summarize(text: str) -> str:
    if len(text) <= _THRESHOLD_CHARS:
        return text

    lines = [_clip_line(line) for line in text.splitlines()]
    total_lines = len(lines)

    head_n = min(_HEAD_LINES, total_lines)
    tail_n = min(_TAIL_LINES, total_lines - head_n)
    tail_start = total_lines - tail_n
    omitted = max(0, tail_start - head_n)

    # Solo líneas relevantes del tramo omitido: las de head/tail ya se ven.
    highlights = [
        f"{number + 1}: {lines[number]}"
        for number in range(head_n, tail_start)
        if _HIGHLIGHT_PATTERN.search(lines[number])
    ]
    truncated_highlights = len(highlights) > _MAX_HIGHLIGHTS
    highlights = highlights[:_MAX_HIGHLIGHTS]

    saved = _persist(text)
    how = f"completo en {saved} (grep / sed -n 'A,Bp')" if saved else "re-ejecutá acotando la salida"
    # Mismo marcador estándar que las capabilities: la telemetría de hooks
    # lo usa para medir si el recorte obligó a volver a buscar.
    sections: list[str] = [
        f"[htx:omitted {omitted} de {total_lines} líneas ({len(text)} chars); {how}]",
    ]
    sections.extend(lines[:head_n])
    if omitted > 0:
        sections.append(f"… ({omitted} líneas omitidas) …")
        if highlights:
            sections.append("[líneas relevantes del tramo omitido]")
            sections.extend(highlights)
            if truncated_highlights:
                sections.append(f"… (más líneas relevantes; primeras {_MAX_HIGHLIGHTS})")
            sections.append("[final]")
    sections.extend(lines[tail_start:])

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
