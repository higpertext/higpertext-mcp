"""Ejecuta una capability in-process, reusando el harness genérico del motor.

Da paridad real con el CLI ('htx task'): normaliza/valida parámetros, valida
el contrato técnico (`contract.rules`) y registra la ejecución — reusando las
mismas funciones puras que `capability_task_service.py` del motor
(`normalize_and_validate_params`, `ContractValidator`, `build_memory_notes`).
El registro de la ejecución YA NO pasa por `save_memory()` del motor (que
escribía a `.memory/` local): va a Redis (`memory.py`) y al profile server
(`profile_client.py`), en paralelo, ambos best-effort.

Qué script correr y su metadata (parámetros, contrato) ya NO se resuelven
contra el JSON local de higpertext-cli: vienen del profile server (ver
`schema.tool_spec_from_capability`, que arma `capability_data`, y `runner.py`,
que trae+cachea el `.py` real vía `profile_client.get_capability_script`).
Lo que sigue viniendo de higpertext-cli es el harness genérico y
capability-agnóstico: el loader de módulos dinámicos (`runner._module_from_script`),
el shim de ejecución in-process (`run_inprocess`), y la validación de
parámetros/contrato (`normalize_and_validate_params`, `ContractValidator`) —
ninguno de esos lee un JSON por-capability.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from higpertext_mcp import discovery, events, execution, memory, profile_client, runner, tracing


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
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "data": self.data,
            "artifacts": self.artifacts,
            "warnings": self.warnings,
            "error": self.error,
            "trace_id": self.trace_id,
        }


def _params_to_argv(capability_id: str, params: dict) -> list[str]:
    argv = [capability_id]
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, list):
            value = ",".join(str(item) for item in value)
        elif isinstance(value, bool):
            value = "true" if value else "false"
        argv.extend([f"--{key}", str(value)])
    return argv


def _localize_params(params: dict) -> dict:
    """Traduce rutas absolutas del host a su path montado en el MCP.

    El agente ve rutas del host; dentro del contenedor el proyecto vive en
    ``HIGPERTEXT_PROJECTS_MOUNT``. Sin esta traducción toda lectura con ruta
    absoluta falla con "no existe" y el agente reintenta a ciegas.
    """
    localized = {}
    for key, value in params.items():
        if isinstance(value, str) and value.startswith(("/", "~")):
            value = str(discovery.local_project_path(value))
        localized[key] = value
    return localized


def _hostify(text: str) -> str:
    """Inversa de `_localize_params` sobre la salida: el agente recibe rutas host."""
    mount = os.environ.get("HIGPERTEXT_PROJECTS_MOUNT", "/projects").rstrip("/")
    host = os.environ.get("HIGPERTEXT_HOST_PROJECTS_ROOT", "").rstrip("/")
    if not host or not text:
        return text
    return text.replace(mount + "/", host + "/")


# Separadores y banners puramente visuales ("=====", "╔──", "[*] Buscando en")
# que los scripts legados imprimen para humanos: tokens sin información.
# No incluye "-": `---` es contenido real en YAML/Markdown.
_DECORATIVE_LINE = re.compile(r"^\s*[=─━═]{5,}\s*$|^\s*[╔╚][─━═].*$|^\s*\[\*\] ")


def _strip_decoration(text: str) -> str:
    text = text.strip()
    try:
        json.loads(text)
        return text  # JSON: salida estructurada, intacta.
    except json.JSONDecodeError:
        pass
    lines = [line for line in text.splitlines() if not _DECORATIVE_LINE.match(line)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


@contextlib.contextmanager
def _cwd(path: Path):
    """Los scripts resuelven rutas relativas contra el cwd. `run_inprocess`
    es síncrono (no cede el event loop), así que el chdir no se mezcla con
    otros requests concurrentes."""
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


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


_ERROR_SUMMARY_CHARS = 600


def _summary(output: str, ok: bool) -> str:
    """Primera línea en éxito; en error, el diagnóstico completo recortado.

    Un error resumido a su primera línea ("[ERROR] <path>") le oculta al
    agente la causa y lo empuja a reintentar a ciegas.
    """
    if not ok:
        text = output.strip()
        return text[:_ERROR_SUMMARY_CHARS] if text else "Capability failed."
    line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if line:
        return line[:240]
    return "Capability completed."


async def _record_activity_best_effort(
    capability_id: str, params: dict, result, contract_ok: bool, contract_errors: list
) -> None:
    # Best-effort en ambos destinos: ni Redis ni el profile server deben poder
    # tumbar la respuesta al cliente MCP (cada uno ya maneja sus propios
    # errores internamente — ver memory.py / profile_client.py).
    root = discovery.resolve_project_root()
    profile = discovery.active_profile(root) or ""
    status = "success" if result.returncode == 0 and contract_ok else "failure"
    notes = execution.build_memory_notes(capability_id, params, result, contract_ok, contract_errors)
    action = f"Auto-run (MCP): {capability_id}"
    await asyncio.gather(
        memory.record_memory(root, action=action, status=status, notes=notes),
        profile_client.record_activity(
            capability_id=capability_id, profile=profile, status=status, summary=notes
        ),
    )


async def call_capability(capability_id: str, params: dict, capability_data: dict) -> CapabilityResult:
    validation = execution.normalize_and_validate_params(capability_data, params)
    if not validation.ok:
        return CapabilityResult(
            ok=False,
            summary="Invalid capability parameters.",
            data={},
            artifacts=[],
            warnings=[],
            error="; ".join(validation.errors),
        )

    root = discovery.resolve_project_root()
    argv = _params_to_argv(capability_id, _localize_params(validation.params))
    trace_id = tracing.current()
    trace_data = {"capability_id": capability_id, "params": validation.params}
    await memory.record_trace_event(
        root, trace_id=trace_id, event=events.EventType.ACTION_REQUESTED.value, data=trace_data
    )
    try:
        script_path = await runner.resolve_script(capability_id)
    except Exception as exc:  # noqa: BLE001 — profile server caído/script inexistente
        await memory.record_trace_event(
            root,
            trace_id=trace_id,
            event=events.EventType.ACTION_FAILED.value,
            data={**trace_data, "stage": "resolve_script", "error": type(exc).__name__},
        )
        return CapabilityResult(
            ok=False,
            summary="Could not fetch capability script from the profile server.",
            data={},
            artifacts=[],
            warnings=[],
            error=str(exc),
        )
    await memory.record_trace_event(
        root, trace_id=trace_id, event=events.EventType.ACTION_STARTED.value, data=trace_data
    )
    with _cwd(root):
        result = execution.run_inprocess(lambda: runner.run_module(script_path, argv[1:]), args=argv)

    contract_ok, contract_errors = True, []
    if result.returncode == 0:
        contract_ok, contract_errors = execution.validate_contract(
            validation.params, result.stdout, result.stderr, result.returncode, capability_data
        )

    ok = result.returncode == 0 and contract_ok
    stdout = _hostify(_strip_decoration(result.stdout))
    stderr = _hostify(result.stderr.strip())
    output = stdout or stderr
    error = None
    if not ok:
        if contract_errors:
            output = (output + "\n" if output else "") + "[CONTRATO] " + "; ".join(contract_errors)
        elif stderr and stderr not in output:
            output = f"{output}\n{stderr}".strip()
        error = output or "Capability failed without diagnostic output."

    await _record_activity_best_effort(
        capability_id, validation.params, result, contract_ok, contract_errors
    )
    terminal_event = (
        events.EventType.ACTION_COMPLETED
        if ok
        else events.EventType.ACTION_FAILED
    )
    await memory.record_trace_event(
        root,
        trace_id=trace_id,
        event=terminal_event.value,
        data={
            "capability_id": capability_id,
            "ok": ok,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "contract_errors": contract_errors,
        },
    )

    return CapabilityResult(
        ok=ok,
        summary=_summary(output, ok),
        data=_result_data(stdout) if ok else {},
        artifacts=[],
        warnings=list(validation.warnings),
        error=error,
        trace_id=trace_id,
    )
