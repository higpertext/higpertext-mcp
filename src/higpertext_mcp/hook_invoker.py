"""Entrypoint estable invocado por el asistente (Claude Code, Codex, ...) para
correr un hook nativo. Es lo único que los settings.json/hooks.json generados
referencian por nombre — el script real del hook se resuelve y cachea en
runtime desde el profile server (ver `hook_runner.py`), así que esta pieza no
cambia nunca aunque el catálogo de hooks se actualice.

Uso: higpertext-hook <hook_id>   (instalado como console_script, ver pyproject.toml)
"""

from __future__ import annotations

import asyncio
import sys

from higpertext_mcp import hook_runner


def main() -> None:
    if len(sys.argv) < 2:
        print('{"continue": true, "error": "uso: higpertext-hook <hook_id>"}')
        sys.exit(0)
    hook_id = sys.argv[1]
    try:
        script_path = asyncio.run(hook_runner.resolve_hook_script(hook_id))
    except Exception as exc:  # noqa: BLE001
        # Un hook que no se puede resolver nunca debe cortar el turno del
        # agente — se deja pasar avisando del error, mismo criterio que
        # hook_io.hook_main en los scripts individuales.
        print(f'{{"continue": true, "error": "{exc}"}}')
        sys.exit(0)
    sys.exit(hook_runner.run_hook(script_path))


if __name__ == "__main__":
    main()
