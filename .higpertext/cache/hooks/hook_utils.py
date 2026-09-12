"""Utilidades compartidas para hook tasks de higpertext — sin dependencia de
higpertext-cli: resuelve la raíz del proyecto leyendo .higpertext/config/
environment.json (o caminando hacia arriba en busca de pyproject.toml)."""

from __future__ import annotations
import json
from pathlib import Path

WORKSPACE_DIR_NAME = ".higpertext"


def get_project_root() -> Path:
    """Resuelve la raíz del proyecto desde environment.json.

    Cuando el hook corre cacheado en .higpertext/cache/hooks/, environment.json
    está en <root>/.higpertext/config/environment.json relativo al CWD del
    proceso que invoca el hook (el asistente siempre lo corre con cwd=raíz del
    proyecto).
    """
    candidates = [
        Path.cwd() / WORKSPACE_DIR_NAME / "config" / "environment.json",
    ]
    for env_path in candidates:
        env_path = env_path.resolve()
        if env_path.exists():
            try:
                data = json.loads(env_path.read_text(encoding="utf-8"))
                root = data.get("system_environment", {}).get("project_root")
                if root:
                    return Path(root)
            except (OSError, json.JSONDecodeError):  # nosec B110
                pass
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".higpertext").exists():
            return candidate
    return cwd
