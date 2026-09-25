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
import hashlib
import importlib.util
import inspect
import sys
from pathlib import Path

from higpertext_mcp import discovery, profile_client

_CACHE_DIR_NAME = ".higpertext/cache/capabilities"
_script_cache: dict[tuple[Path, str], Path] = {}


def _package_name(parent: Path) -> str:
    """Devuelve un paquete sintético único por carpeta de caché.

    El MCP puede atender varios proyectos en el mismo proceso. Si todos usan
    el nombre basado sólo en ``capabilities``, los imports relativos pueden
    resolver helpers del primer proyecto atendido.
    """
    digest = hashlib.sha256(str(parent.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"higpertext_mcp_dynamic_{digest}"


def _module_from_script(script_path: Path):
    """Carga un script cacheado con un paquete sintético para imports relativos.

    Implementación local deliberada: el MCP ya no requiere higpertext-cli para
    ejecutar los scripts que el profile server le entrega.
    """
    parent = script_path.parent
    package = _package_name(parent)
    if package not in sys.modules:
        spec = importlib.util.spec_from_loader(package, loader=None, is_package=True)
        if spec is None:
            raise ImportError(f"no se pudo crear paquete para {parent}")
        module = importlib.util.module_from_spec(spec)
        module.__path__ = [str(parent)]
        sys.modules[package] = module
    full_name = f"{package}.{script_path.stem}"
    spec = importlib.util.spec_from_file_location(
        full_name, script_path, submodule_search_locations=[str(parent)]
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"no se pudo cargar {script_path}")
    module = importlib.util.module_from_spec(spec)
    module.__package__ = package
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def _cache_path(root: Path, capability_id: str) -> Path:
    safe_name = capability_id.replace(".", "_").replace("/", "_")
    return root / _CACHE_DIR_NAME / f"{safe_name}.py"


async def resolve_script(capability_id: str) -> Path:
    """Path local (cacheado en memoria por proceso) al script de la capability,
    descargado del profile server y escrito a `.higpertext/cache/capabilities/`.
    """
    root = discovery.resolve_project_root()
    cache_key = (root, capability_id)
    cached = _script_cache.get(cache_key)
    if cached is not None:
        return cached

    fetched = await profile_client.get_capability_script(capability_id)
    if fetched is None:
        raise RuntimeError(f"no se pudo obtener el script de {capability_id} del profile server")
    source_code_b64, _language, extra_files = fetched

    path = _cache_path(root, capability_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(source_code_b64))

    # Helpers hermanos (ej. "_report_paths.py", o subpaquetes como
    # "_parser_language/base.py") van al mismo directorio flat de cache — el
    # import relativo del entrypoint (`from ._report_paths import ...`) los
    # busca junto a sí mismo, sin importar qué otra capability los haya
    # escrito ahí primero (mismo contenido, se pisan sin problema).
    for filename, content_b64 in extra_files.items():
        relative = Path(filename)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"helper de capability fuera del cache permitido: {filename!r}")
        dest = path.parent / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(content_b64))

    _script_cache[cache_key] = path
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
