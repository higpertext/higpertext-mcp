"""Ejecuta una capability in-process, reusando el dispatcher del motor.

No reimplementa carga de módulos ni manejo de argparse/SystemExit: eso ya lo
resuelve `capabilities_runner.main_inprocess`. Este módulo solo traduce un dict de
parámetros a argv y captura stdout/stderr sin lanzar un subprocess.

Limitación conocida (documentada, no oculta): `capabilities_runner` resuelve rutas
del proyecto (`_PROJECT_EXTERNAL_CAPS`, `_PROJECT_SOURCE_CAPS`) usando `Path.cwd()`
evaluado en el momento del import del módulo. Esto es correcto siempre que el
proceso del servidor MCP se lance una vez por proyecto con ese cwd ya fijo (el
patrón estándar de un server MCP local declarado en `.mcp.json`); NO sirve para un
server compartido entre múltiples proyectos en el mismo proceso.
"""

from __future__ import annotations

from dataclasses import dataclass

from higpertext.capabilities import capabilities_runner
from higpertext.kernel.infrastructure.cli.execution_result import run_inprocess


@dataclass
class CapabilityResult:
    ok: bool
    output: str


def _params_to_argv(capability_id: str, params: dict) -> list[str]:
    argv = [capability_id]
    for key, value in params.items():
        if value is None:
            continue
        argv.extend([f"--{key}", str(value)])
    return argv


def call_capability(capability_id: str, params: dict) -> CapabilityResult:
    argv = _params_to_argv(capability_id, params)
    result = run_inprocess(lambda: capabilities_runner.main_inprocess(argv), args=argv)
    ok = result.returncode == 0
    output = result.stdout.strip() or result.stderr.strip()
    if not ok and result.stderr.strip() and result.stderr.strip() not in output:
        output = f"{output}\n{result.stderr.strip()}".strip()
    return CapabilityResult(ok=ok, output=output)
