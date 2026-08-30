"""Ejecuta una capability in-process, reusando el dispatcher del motor.

Da paridad real con el CLI ('htx task'): normaliza/valida parámetros, valida
el contrato técnico (`contract.rules`) y registra la ejecución en `.memory/` —
reusando las mismas funciones puras que `capability_task_service.py` del motor
(`normalize_and_validate_params`, `ContractValidator`, `save_memory`,
`build_memory_notes`). Deliberadamente NO pasa por `HigpertextHub`/`ROOT_DIR`
de `router.py`: en modo desarrollo (paquete `higpertext` resuelto por `sys.path`,
no instalado en site-packages) `ROOT_DIR` resuelve siempre al repo de
higpertext-cli sin importar el cwd del proceso — exactamente el patrón que
`discovery.py` documenta evitar para no romper el soporte multi-proyecto.

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
from higpertext.capabilities.common.scripts.core.governance.memory_manager import (
    save_memory,
)
from higpertext.kernel.infrastructure.cli.execution_result import run_inprocess
from higpertext.kernel.infrastructure.cli.parameter_contracts import (
    normalize_and_validate_params,
)
from higpertext.kernel.infrastructure.cli.task_result_reporter import build_memory_notes
from higpertext.kernel.infrastructure.validation.contract_validator import ContractValidator


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


def _save_memory_best_effort(
    capability_id: str, params: dict, result, contract_ok: bool, contract_errors: list
) -> None:
    # Best-effort: un fallo al persistir memoria nunca debe tumbar la respuesta
    # al cliente MCP, y jamás debe escribir a stdout (rompería el protocolo
    # stdio de MCP).
    try:
        notes = build_memory_notes(capability_id, params, result, contract_ok, contract_errors)
        save_memory(
            action=f"Auto-run (MCP): {capability_id}",
            status="success" if result.returncode == 0 and contract_ok else "failure",
            notes=notes,
        )
    except (OSError, ValueError):
        pass


def call_capability(capability_id: str, params: dict, capability_data: dict) -> CapabilityResult:
    validation = normalize_and_validate_params(capability_data, params)
    if not validation.ok:
        return CapabilityResult(
            ok=False,
            output="[ERROR] Parámetros inválidos:\n"
            + "\n".join(f"- {e}" for e in validation.errors),
        )

    argv = _params_to_argv(capability_id, validation.params)
    result = run_inprocess(lambda: capabilities_runner.main_inprocess(argv), args=argv)

    contract_ok, contract_errors = True, []
    if result.returncode == 0:
        contract_ok, contract_errors = ContractValidator.validate(
            validation.params, result.stdout, result.stderr, result.returncode, capability_data
        )

    ok = result.returncode == 0 and contract_ok
    output = result.stdout.strip() or result.stderr.strip()
    if not ok:
        if contract_errors:
            output = (output + "\n" if output else "") + "[CONTRATO] " + "; ".join(contract_errors)
        elif result.stderr.strip() and result.stderr.strip() not in output:
            output = f"{output}\n{result.stderr.strip()}".strip()

    _save_memory_best_effort(capability_id, validation.params, result, contract_ok, contract_errors)

    return CapabilityResult(ok=ok, output=output)
