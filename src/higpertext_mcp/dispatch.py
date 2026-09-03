"""Ejecuta una capability in-process, reusando el dispatcher del motor.

Da paridad real con el CLI ('htx task'): normaliza/valida parámetros, valida
el contrato técnico (`contract.rules`) y registra la ejecución — reusando las
mismas funciones puras que `capability_task_service.py` del motor
(`normalize_and_validate_params`, `ContractValidator`, `build_memory_notes`).
El registro de la ejecución YA NO pasa por `save_memory()` del motor (que
escribía a `.memory/` local): va a Redis (`memory.py`) y al profile server
(`profile_client.py`), en paralelo, ambos best-effort. Deliberadamente NO pasa
por `HigpertextHub`/`ROOT_DIR` de `router.py`: en modo desarrollo (paquete
`higpertext` resuelto por `sys.path`, no instalado en site-packages) `ROOT_DIR`
resuelve siempre al repo de higpertext-cli sin importar el cwd del proceso —
exactamente el patrón que `discovery.py` documenta evitar para no romper el
soporte multi-proyecto.

Limitación conocida (documentada, no oculta): `capabilities_runner` resuelve rutas
del proyecto (`_PROJECT_EXTERNAL_CAPS`, `_PROJECT_SOURCE_CAPS`) usando `Path.cwd()`
evaluado en el momento del import del módulo. Esto es correcto siempre que el
proceso del servidor MCP se lance una vez por proyecto con ese cwd ya fijo (el
patrón estándar de un server MCP local declarado en `.mcp.json`); NO sirve para un
server compartido entre múltiples proyectos en el mismo proceso.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from higpertext.capabilities import capabilities_runner
from higpertext.kernel.infrastructure.cli.execution_result import run_inprocess
from higpertext.kernel.infrastructure.cli.parameter_contracts import (
    normalize_and_validate_params,
)
from higpertext.kernel.infrastructure.cli.task_result_reporter import build_memory_notes
from higpertext.kernel.infrastructure.validation.contract_validator import ContractValidator

from higpertext_mcp import discovery, memory, profile_client


@dataclass
class CapabilityResult:
    """Resultado agnóstico de transporte de una capability.

    ``output`` se conservaba como texto opaco porque el CLI heredó el contrato
    stdin/stdout de los scripts. Los clientes agénticos no deben depender de
    ese formato: reciben este sobre estable y pueden usar ``data`` sin
    interpretar prefijos como ``[SUCCESS]`` o logs de consola.
    """

    ok: bool
    summary: str
    data: dict[str, Any]
    artifacts: list[str]
    warnings: list[str]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "data": self.data,
            "artifacts": self.artifacts,
            "warnings": self.warnings,
            "error": self.error,
        }


def _params_to_argv(capability_id: str, params: dict) -> list[str]:
    argv = [capability_id]
    for key, value in params.items():
        if value is None:
            continue
        argv.extend([f"--{key}", str(value)])
    return argv


def _result_data(output: str) -> dict[str, Any]:
    """Convierte JSON emitido por una capability en datos; encapsula texto legado.

    La envoltura ``text`` es una compatibilidad temporal para las capabilities
    que aún imprimen texto. El protocolo MCP nunca expone ese texto como la
    respuesta principal del tool.
    """
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return {"text": output} if output else {}
    return parsed if isinstance(parsed, dict) else {"items": parsed}


def _summary(output: str, ok: bool) -> str:
    line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if line:
        return line[:240]
    return "Capability completed." if ok else "Capability failed."


async def _record_activity_best_effort(
    capability_id: str, params: dict, result, contract_ok: bool, contract_errors: list
) -> None:
    # Best-effort en ambos destinos: ni Redis ni el profile server deben poder
    # tumbar la respuesta al cliente MCP (cada uno ya maneja sus propios
    # errores internamente — ver memory.py / profile_client.py).
    root = discovery.resolve_project_root()
    profile = discovery.active_profile(root) or ""
    status = "success" if result.returncode == 0 and contract_ok else "failure"
    notes = build_memory_notes(capability_id, params, result, contract_ok, contract_errors)
    action = f"Auto-run (MCP): {capability_id}"
    await asyncio.gather(
        memory.record_memory(root, action=action, status=status, notes=notes),
        profile_client.record_activity(
            capability_id=capability_id, profile=profile, status=status, summary=notes
        ),
    )


async def call_capability(capability_id: str, params: dict, capability_data: dict) -> CapabilityResult:
    validation = normalize_and_validate_params(capability_data, params)
    if not validation.ok:
        return CapabilityResult(
            ok=False,
            summary="Invalid capability parameters.",
            data={},
            artifacts=[],
            warnings=[],
            error="; ".join(validation.errors),
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
    error = None
    if not ok:
        if contract_errors:
            output = (output + "\n" if output else "") + "[CONTRATO] " + "; ".join(contract_errors)
        elif result.stderr.strip() and result.stderr.strip() not in output:
            output = f"{output}\n{result.stderr.strip()}".strip()
        error = output or "Capability failed without diagnostic output."

    await _record_activity_best_effort(
        capability_id, validation.params, result, contract_ok, contract_errors
    )

    return CapabilityResult(
        ok=ok,
        summary=_summary(output, ok),
        data=_result_data(result.stdout.strip()) if ok else {},
        artifacts=[],
        warnings=list(validation.warnings),
        error=error,
    )
