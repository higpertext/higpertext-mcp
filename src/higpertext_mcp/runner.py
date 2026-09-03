"""Resuelve y ejecuta el script de una capability sin depender del JSON local
de higpertext-cli para saber *cuál* archivo correr — eso ahora lo dice el
profile server (`profile_client.get_capability_script`). La carga dinámica
del módulo (truco de paquete sintético para que un script pueda importar
hermanos vía import relativo) sí sigue siendo la de higpertext-cli
(`capabilities_runner._module_from_script`): es genérica, no depende de
ningún JSON por-capability, así que no hay razón para duplicarla.
"""

from __future__ import annotations

import base64
import inspect
import sys
from pathlib import Path

from higpertext.capabilities.capabilities_runner import _module_from_script

from higpertext_mcp import discovery, profile_client

_CACHE_DIR_NAME = ".higpertext/cache/capabilities"
_script_cache: dict[str, Path] = {}


def _cache_path(root: Path, capability_id: str) -> Path:
    safe_name = capability_id.replace(".", "_").replace("/", "_")
    return root / _CACHE_DIR_NAME / f"{safe_name}.py"


async def resolve_script(capability_id: str) -> Path:
    """Path local (cacheado en memoria por proceso) al script de la capability,
    descargado del profile server y escrito a `.higpertext/cache/capabilities/`.
    """
    cached = _script_cache.get(capability_id)
    if cached is not None:
        return cached

    fetched = await profile_client.get_capability_script(capability_id)
    if fetched is None:
        raise RuntimeError(f"no se pudo obtener el script de {capability_id} del profile server")
    source_code_b64, _language, extra_files = fetched

    root = discovery.resolve_project_root()
    path = _cache_path(root, capability_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(source_code_b64))

    # Helpers hermanos (ej. "_report_paths.py") van al mismo directorio flat
    # de cache — el import relativo del entrypoint (`from ._report_paths
    # import ...`) los busca junto a sí mismo, sin importar qué otra
    # capability los haya escrito ahí primero (mismo contenido, se pisan sin
    # problema).
    for filename, content_b64 in extra_files.items():
        (path.parent / filename).write_bytes(base64.b64decode(content_b64))

    _script_cache[capability_id] = path
    return path


def _run_module_main(module, call_args: list[str]) -> int:
    """Invoca `module.main(...)` fuera de proceso-de-verdad (mismo intérprete),
    replicando el shim de `capabilities_runner.main_inprocess`: algunas
    capabilities parsean argparse leyendo `sys.argv` global en vez de recibir
    argumentos, así que se sustituye temporalmente.
    """
    sig = inspect.signature(module.main)
    original_argv = sys.argv
    sys.argv = [original_argv[0] if original_argv else "capability", *call_args]
    try:
        if sig.parameters:
            module.main(call_args)
        else:
            module.main()
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    finally:
        sys.argv = original_argv
    return 0


def run_module(script_path: Path, call_args: list[str]) -> int:
    """Parte síncrona: cargar+ejecutar. Separada de `resolve_script` (async,
    hace la llamada gRPC) porque `run_inprocess` (higpertext-cli) espera un
    callable sync — el fetch+cache del script tiene que pasar *antes*, no
    dentro del `lambda` que arma `dispatch.call_capability`.
    """
    module = _module_from_script(script_path)
    return _run_module_main(module, call_args)
