"""Registro local y verificable de los renderizados de un proyecto."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REGISTRY_DIR = Path(".higpertext/state/renders")


def _collect_paths(value: Any, *, key: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for child_key, child in value.items():
            paths.extend(_collect_paths(child, key=child_key))
    elif isinstance(value, list) and key in {"files", "written", "pruned", "removed", "skipped_unmanaged"}:
        paths.extend(item for item in value if isinstance(item, str))
    return paths


def _hash_files(root: Path, paths: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in sorted(set(paths)):
        candidate = Path(relative)
        # Los renderizadores sólo deben producir rutas relativas al proyecto.
        # Ignorar rutas absolutas o con ``..`` evita que un resultado corrupto
        # convierta al registro en un lector accidental fuera del tenant.
        if candidate.is_absolute() or ".." in candidate.parts:
            continue
        path = root / candidate
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[relative] = digest
    return hashes


def record_render(
    root: Path,
    *,
    project_id: str,
    profile: str,
    assistants: list[str],
    result: dict[str, Any],
    status: str = "success",
    error: str | None = None,
) -> dict[str, Any]:
    """Persiste un manifiesto atómico después de un render.

    El contenido de los archivos nunca se copia al manifiesto: sólo se guarda
    hash, ruta relativa y resultado. Así el registro sirve para detectar drift
    sin duplicar prompts, código o secretos.
    """
    root = root.resolve()
    render_id = f"rnd_{uuid.uuid4().hex}"
    paths = _collect_paths(result)
    manifest: dict[str, Any] = {
        "render_id": render_id,
        "project_id": project_id,
        "profile": profile,
        "assistants": list(assistants),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "written": result.get("files", []),
        "removed": result.get("removed", []),
        "outputs": {
            key: value for key, value in result.items()
            if key not in {"files", "removed"}
        },
        "content_hashes": _hash_files(root, paths),
    }
    if error:
        manifest["error"] = error

    directory = root / _REGISTRY_DIR
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{render_id}.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
    return {"render_id": render_id, "manifest": str(destination.relative_to(root)), "status": status}


def list_renders(root: Path, *, limit: int = 20) -> list[dict[str, Any]]:
    directory = root / _REGISTRY_DIR
    if not directory.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("rnd_*.json"), reverse=True):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
        if len(records) >= limit:
            break
    return records
