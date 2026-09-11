"""Resuelve y ejecuta el script de un hook nativo (PreToolUse/PostToolUse/...)
sin depender de higpertext-cli ni de una copia materializada por proyecto:
el script + sus dependencias compartidas (hook_utils.py, hook_io.py, _rules/*)
se descargan del profile server y se cachean en
`.higpertext/cache/hooks/` — mismo patrón que `runner.py` usa para capabilities.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from higpertext_mcp import discovery, profile_client
from higpertext_mcp import runner

_CACHE_DIR_NAME = ".higpertext/cache/hooks"


def _cache_dir(root: Path) -> Path:
    path = root / _CACHE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_hook_project_root() -> Path:
    """Raíz de proyecto para el CLI `higpertext-hook`.

    A diferencia de `discovery.resolve_project_root()` (pensado para el
    proceso MCP de larga vida, que puede servir a más de un proyecto y por
    eso nunca confía en su propio cwd), este CLI es un subproceso nuevo por
    cada invocación que el asistente (Claude Code, etc.) siempre lanza con
    cwd = raíz del proyecto activo — cae a Path.cwd() cuando no hay
    HIGPERTEXT_PROJECT_ROOT explícito, en vez de exigirlo y fallar.
    """
    override = os.environ.get("HIGPERTEXT_PROJECT_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path.cwd()


async def resolve_hook_script(hook_id: str) -> Path:
    """Path local al script del hook, escrito (junto a sus shared assets) en
    `.higpertext/cache/hooks/` del proyecto actual."""
    root = _resolve_hook_project_root()
    cache_dir = _cache_dir(root)

    source_code_b64 = await profile_client.get_hook_script(hook_id)
    if source_code_b64 is None:
        raise RuntimeError(f"no se pudo obtener el script del hook {hook_id} del profile server")
    script_path = cache_dir / f"{hook_id}.py"
    script_path.write_bytes(base64.b64decode(source_code_b64))

    assets = await profile_client.get_shared_hook_assets()
    for relative, content_b64 in assets.items():
        dest = cache_dir / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(content_b64))

    await _write_profile_rules(cache_dir, root)
    return script_path


async def _write_profile_rules(cache_dir: Path, root: Path) -> None:
    """Genera _rules/profile_rules.json a partir de GovernanceRule con
    `pattern` no vacío — reemplaza el JSON estático que antes se empaquetaba
    con el hook: una regla creada vía higpertext-governance-rule (MCP) queda
    activa acá en la siguiente invocación del hook, sin re-render ni rebuild.
    """
    profile = discovery.active_profile(root) or ""
    try:
        rules = await profile_client.list_governance_rules()
    except Exception:  # noqa: BLE001 — best-effort: sin profile server, sin reglas dinámicas
        rules = []
    # check_profile_rules solo distingue "block" (corta la tool call) vs
    # "context" (avisa y deja continuar) — mapeo desde la Severity de
    # gobernanza: CRITICAL/HIGH bloquean, MEDIUM/LOW solo avisan.
    _blocking = {profile_client.profile_pb2.Severity.CRITICAL, profile_client.profile_pb2.Severity.HIGH}
    entries = [
        {
            "pattern": r.pattern,
            "severity": "block" if r.severity in _blocking else "context",
            "capability": r.capability,
            "reason": r.description,
        }
        for r in rules
        if r.pattern and (r.source == "global" or r.source == profile)
    ]
    dest = cache_dir / "_rules" / "profile_rules.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"rules": entries}, ensure_ascii=False, indent=2), encoding="utf-8")


def run_hook(script_path: Path) -> int:
    """Carga el script cacheado (con sus shared assets al lado) y ejecuta su
    main() — los hooks leen el payload de stdin directamente, sin argumentos."""
    return runner.run_module(script_path, [])
