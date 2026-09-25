"""Resuelve y ejecuta el script de un hook nativo (PreToolUse/PostToolUse/...)
sin depender de higpertext-cli ni de una copia materializada por proyecto:
el script + sus dependencias compartidas (hook_utils.py, hook_io.py, _rules/*)
se descargan del profile server y se cachean en
`.higpertext/cache/hooks/` — mismo patrón que `runner.py` usa para capabilities.

Concurrencia: Claude Code corre en paralelo todos los hooks que matchean una
tool call (y los PostToolUse de la anterior pueden seguir vivos), y cada
invocación re-descarga todo. Antes cada una reescribía los mismos archivos
en `.higpertext/cache/hooks/` mientras otras importaban de ahí, con dos
fallas intermitentes reales:

- write_bytes trunca y escribe: un hook concurrente importaba un .py vacío
  (ImportError -> deny fail-closed) o leía un profile_rules.json truncado
  (JSONDecodeError -> check_profile_rules devolvía None: reglas de perfil sin
  aplicar, fail-OPEN).
- aun con escritura atómica (os.replace), el FileFinder de Python lista el
  directorio para importar y un readdir concurrente con un rename puede no
  devolver la entrada (btrfs): ModuleNotFoundError sobre un archivo existente.

Por eso el hook se ejecuta desde un bundle INMUTABLE direccionado por
contenido (`.higpertext/cache/hooks/.v/<sha256>/`): se arma en un directorio
temporal y se publica con un único rename de directorio; una vez publicado
nadie lo modifica, así ningún import compite con una escritura. Los archivos
de primer nivel se siguen escribiendo (atómicamente) porque hay consumidores
que los referencian por ruta fija (ej. `_rules/output_filter.py` en el
comando reescrito por hook_bash_output_rewrite) y porque su mtime es la
evidencia de fetch fresco que usa common.server-verification-report.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from higpertext_mcp import discovery, profile_client
from higpertext_mcp import runner

_CACHE_DIR_NAME = ".higpertext/cache/hooks"
_BUNDLES_DIR_NAME = ".v"
# Bundles sin uso más viejos que esto se borran. Generoso a propósito: un
# hook en curso nunca debe perder su bundle bajo los pies.
_BUNDLE_TTL_SECONDS = 24 * 3600


def _cache_dir(root: Path) -> Path:
    path = root / _CACHE_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_atomic(dest: Path, data: bytes) -> None:
    """Reemplaza dest de forma atómica (temp en el mismo dir + os.replace):
    un lector ve el archivo viejo o el nuevo, nunca uno parcial."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, 0o644)
        os.replace(tmp, dest)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _publish_bundle(cache_dir: Path, files: dict[str, bytes]) -> Path:
    """Materializa files en `.v/<sha256>/` si no existe y devuelve esa ruta.

    El directorio se arma completo en un temporal y se publica con
    os.rename: si otro proceso ganó la carrera con el mismo contenido, el
    rename falla (destino no vacío) y se descarta el temporal.
    """
    digest = hashlib.sha256()
    for relative in sorted(files):
        digest.update(relative.encode("utf-8") + b"\0" + hashlib.sha256(files[relative]).digest())
    bundles = cache_dir / _BUNDLES_DIR_NAME
    final = bundles / digest.hexdigest()[:32]
    if final.is_dir():
        with contextlib.suppress(OSError):
            os.utime(final)  # marca de uso para el TTL
        return final

    bundles.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(dir=bundles, prefix=f".{final.name}.", suffix=".tmp"))
    try:
        for relative, data in files.items():
            dest = tmp / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        os.chmod(tmp, 0o755)
        try:
            os.rename(tmp, final)
        except OSError:
            if not final.is_dir():
                raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _prune_bundles(bundles, keep=final)
    return final


def _prune_bundles(bundles: Path, keep: Path) -> None:
    """Borra bundles (y temporales abandonados) sin uso hace más de TTL."""
    cutoff = time.time() - _BUNDLE_TTL_SECONDS
    for entry in bundles.iterdir():
        if entry == keep:
            continue
        with contextlib.suppress(OSError):
            if entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry, ignore_errors=True)


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
    """Path al script del hook dentro de su bundle inmutable (script + shared
    assets + profile_rules.json), descargado fresco del profile server."""
    root = _resolve_hook_project_root()
    cache_dir = _cache_dir(root)

    source_code_b64 = await profile_client.get_hook_script(hook_id)
    if source_code_b64 is None:
        raise RuntimeError(f"no se pudo obtener el script del hook {hook_id} del profile server")
    files: dict[str, bytes] = {f"{hook_id}.py": base64.b64decode(source_code_b64)}

    assets = await profile_client.get_shared_hook_assets()
    for relative, content_b64 in assets.items():
        files[relative] = base64.b64decode(content_b64)

    files["_rules/profile_rules.json"] = await _render_profile_rules(root)

    # Compat: copia de primer nivel para consumidores por ruta fija y como
    # evidencia (mtime) de fetch fresco. Nunca se importa desde acá.
    for relative, data in files.items():
        _write_atomic(cache_dir / relative, data)

    return _publish_bundle(cache_dir, files) / f"{hook_id}.py"


async def _render_profile_rules(root: Path) -> bytes:
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
    return json.dumps({"rules": entries}, ensure_ascii=False, indent=2).encode("utf-8")


def run_hook(script_path: Path) -> int:
    """Carga el script cacheado (con sus shared assets al lado) y ejecuta su
    main() — los hooks leen el payload de stdin directamente, sin argumentos."""
    return runner.run_module(script_path, [])
