"""Replay de context misses sobre sesiones reales de Claude Code.

Responde "¿recortar salidas deja al agente sin el contexto que necesita?"
con datos, antes de cambiar un umbral en vivo. Para cada salida histórica de
Bash en los transcripts (``~/.claude/projects/<proyecto>/*.jsonl``) aplica el
filtro de salida VIGENTE (``_rules/output_filter.py`` del caché de hooks del
proyecto, o ``--filter``) con cada umbral pedido, y cuenta:

- recortes: salidas que el filtro habría resumido;
- misses: recortes tras los cuales el agente usó, en sus siguientes
  ``--lookahead`` turnos, un identificador específico (snake_case,
  CamelCase, ruta o nombre con punto) que SOLO estaba en la parte omitida.
  Es una cota superior: el agente puede escribir un identificador por
  conocimiento propio, no por haberlo leído;
- ahorro: tokens (chars/4) que el filtro habría quitado del contexto.

Complementa la métrica en vivo (resource MCP ``higpertext://session/usage`` →
``context_misses``), que mide misses reales a medida que se acumula telemetría.

Uso:
    python scripts/context_miss_replay.py --project higpertext-mcp --project content \\
        --threshold 6000 --threshold 20000
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import re
from collections import Counter
from pathlib import Path

_TOKEN = re.compile(r"\b(?:[a-z]+_[a-z0-9_]{3,}|[A-Z][a-z]+[A-Z][A-Za-z]{2,}|[\w-]+(?:[./][\w-]+){1,})\b")
_PROJECTS_DIR = Path("~/.claude/projects").expanduser()
_HOST_PROJECTS_PREFIX = "-home-aomerge-Documentos-Proyects-"


def load_filter(path: Path):
    spec = importlib.util.spec_from_file_location("htx_output_filter", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"no se pudo cargar el filtro: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._persist = lambda _text: "/tmp/higpertext-outputs/replay.log"  # nunca escribe a disco
    return module


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block.get("text", "") for block in content if isinstance(block, dict))
    return ""


def _assistant_text(message: dict) -> str:
    parts = []
    for block in message.get("content") or []:
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            parts.append(json.dumps(block.get("input", {}), ensure_ascii=False))
    return "\n".join(parts)


def _messages(path: str) -> list[dict]:
    messages = []
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = entry.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), list):
            messages.append(message)
    return messages


def bash_outputs(paths: list[str], lookahead: int):
    """(comando, salida, texto de los siguientes turnos del asistente) por cada Bash."""
    for path in paths:
        messages = _messages(path)
        tool_uses = {}
        for index, message in enumerate(messages):
            for block in message["content"]:
                if block.get("type") == "tool_use":
                    tool_uses[block["id"]] = (block["name"], block.get("input", {}))
                if block.get("type") != "tool_result":
                    continue
                name, tool_input = tool_uses.get(block.get("tool_use_id"), ("?", {}))
                if name != "Bash":
                    continue
                following = [m for m in messages[index + 1 :] if m.get("role") == "assistant"][:lookahead]
                yield str(tool_input.get("command", "")), _text(block.get("content")), "\n".join(
                    _assistant_text(m) for m in following
                )


def replay(samples: list[tuple[str, str, str]], output_filter, threshold: int) -> Counter:
    output_filter._THRESHOLD_CHARS = threshold
    stats: Counter = Counter()
    for command, output, later in samples:
        summary = output_filter.summarize(output)
        stats["before"] += len(output)
        stats["after"] += len(summary)
        if summary == output:
            continue
        stats["truncated"] += 1
        kept = set(_TOKEN.findall(summary)) | set(_TOKEN.findall(command))
        if any(token in later for token in set(_TOKEN.findall(output)) - kept):
            stats["misses"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--project", action="append", required=True, help="nombre del directorio del proyecto")
    parser.add_argument("--threshold", action="append", type=int, help="umbral en chars (repetible)")
    parser.add_argument("--lookahead", type=int, default=6, help="turnos del asistente a revisar tras cada recorte")
    parser.add_argument("--filter", type=Path, help="output_filter.py a evaluar (default: caché de hooks del proyecto actual)")
    args = parser.parse_args()

    filter_path = args.filter or Path.cwd() / ".higpertext/cache/hooks/_rules/output_filter.py"
    output_filter = load_filter(filter_path)
    thresholds = args.threshold or [output_filter._THRESHOLD_CHARS]
    paths = [
        path
        for project in args.project
        for path in glob.glob(str(_PROJECTS_DIR / f"{_HOST_PROJECTS_PREFIX}{project}" / "*.jsonl"))
    ]
    samples = list(bash_outputs(paths, args.lookahead))
    print(f"{len(paths)} sesiones, {len(samples)} salidas de Bash — filtro: {filter_path}")
    print(f"{'umbral':>8} {'recortes':>9} {'misses':>7} {'miss%':>6} {'ahorro%':>8} {'tokens_ahorrados':>17}")
    for threshold in thresholds:
        stats = replay(samples, output_filter, threshold)
        saved = stats["before"] - stats["after"]
        print(
            f"{threshold:>8} {stats['truncated']:>9} {stats['misses']:>7} "
            f"{100 * stats['misses'] / max(1, stats['truncated']):>6.1f} "
            f"{100 * saved / max(1, stats['before']):>8.1f} {saved // 4:>17}"
        )


if __name__ == "__main__":
    main()
