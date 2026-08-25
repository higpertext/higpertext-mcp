"""Resuelve raíz de proyecto, perfil activo y capabilities permitidas.

Usa resolución basada en cwd — el mismo patrón que higpertext-cli usa para sus
hooks (`hook_utils.get_project_root`) — NO `higpertext.kernel.config_paths.PROJECT_ROOT`,
que resuelve la raíz del *motor instalado*, no la del proyecto destino. Ver
docs/architecture.md para el porqué de esta distinción.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

V1_CAPABILITY_IDS: frozenset[str] = frozenset(
    {
        "common.grep-search",
        "git.diff",
        "git.ls-files",
        "common.smart-read",
        "common.code-skeletonizer",
        "common.knowledge-asker",
        "common.memory-manager",
        "git.committer",
        "security.secret-scanner",
        "common.quality-resolver",
    }
)

_WORKSPACE_DIR = ".higpertext"


def resolve_project_root() -> Path:
    """Raíz del proyecto destino: override explícito o cwd del proceso servidor."""
    override = os.environ.get("HIGPERTEXT_PROJECT_ROOT")
    if override:
        return Path(override).resolve()
    return Path.cwd()


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def active_profile(root: Path) -> str | None:
    env = _read_json(root / _WORKSPACE_DIR / "config" / "environment.json")
    return env.get("active_profile") or None


def profile_capability_ids(root: Path, profile: str) -> list[str]:
    profile_file = root / "src" / "config" / "profiles" / f"{profile}.json"
    data = _read_json(profile_file)
    return list(data.get("capabilities", []))


def allowed_capability_ids(root: Path) -> list[str]:
    """Intersección entre el set fijo de v1 y lo que el perfil activo permite.

    Fail-closed: sin perfil activo o sin perfil legible, no se expone nada.
    """
    profile = active_profile(root)
    if not profile:
        return []
    granted = set(profile_capability_ids(root, profile))
    return sorted(V1_CAPABILITY_IDS & granted)
