"""Harness mínimo de ejecución y contratos, independiente de higpertext-cli."""
from __future__ import annotations

import contextlib
import io
import re
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class Validation:
    ok: bool
    params: dict[str, Any]
    errors: list[str]
    warnings: list[str]


def normalize_and_validate_params(definition: dict, supplied: dict) -> Validation:
    params = dict(supplied or {})
    errors: list[str] = []
    declared = {item.get("name"): item for item in definition.get("parameters", []) if item.get("name")}
    for name, spec in declared.items():
        if name not in params and "default" in spec:
            params[name] = spec["default"]
        if spec.get("required") and (name not in params or params[name] in (None, "")):
            errors.append(f"missing required parameter: {name}")
    unknown = sorted(set(params) - set(declared))
    if unknown:
        errors.extend(f"unknown parameter: {name}" for name in unknown)
    return Validation(not errors, params, errors, [])


def run_inprocess(fn: Callable[[], int], args: list[str]) -> ExecutionResult:
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = fn()
        return ExecutionResult(int(code or 0), stdout.getvalue(), stderr.getvalue())
    except Exception as exc:  # noqa: BLE001
        return ExecutionResult(1, stdout.getvalue(), stderr.getvalue() + f"{type(exc).__name__}: {exc}\n")


def validate_contract(params: dict, stdout: str, stderr: str, returncode: int, definition: dict) -> tuple[bool, list[str]]:
    if returncode:
        return False, [f"exit code {returncode}"]
    contract = definition.get("contract", {})
    pattern = contract.get("success_pattern")
    if pattern and not re.search(pattern, stdout, re.MULTILINE):
        return False, [f"success_pattern not found: {pattern}"]
    return True, []


def build_memory_notes(capability_id: str, params: dict, result: ExecutionResult, contract_ok: bool, errors: list) -> str:
    status = "success" if result.returncode == 0 and contract_ok else "failure"
    return f"{capability_id}: {status}; params={params}; contract_errors={errors}"
