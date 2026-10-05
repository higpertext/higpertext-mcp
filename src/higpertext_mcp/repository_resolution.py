"""RFC-0020 fase 3: el perfil activo de un repositorio viene del servidor.

Antes, el perfil activo de cada checkout salía de
`<root>/.higpertext/config/environment.json`: un archivo por carpeta, invisible
para el servidor. Ahora la fuente es `RepositoryConfig.profile` (precedencia
repositorio > proyecto > global).

El archivo ya no se lee de forma permanente: si el repositorio aún no tiene perfil
en el servidor, el del archivo se ADOPTA UNA VEZ (se copia al servidor, ver
`adopt_legacy_profile`) y desde entonces el servidor manda; cambiar el archivo no
cambia nada. HIGPERTEXT_PROFILE_SOURCE=local conserva el comportamiento anterior.

Si el profile server no responde, `server_profile` devuelve el último valor bueno
que se conoció (si lo hay) o None: ante un servidor caído no se inventa un perfil.
Resolver el repositorio es un get-or-create en el servidor: un repo nuevo queda
registrado (y su Project resuelto desde la raíz de git) sin pasos manuales.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from higpertext_mcp import config, profile_client

_TTL_S = 30.0       # cuánto se reutiliza una respuesta del servidor
_NEGATIVE_TTL_S = 5.0  # tras un fallo no se insiste en cada llamada
_cache: dict[str, tuple[float, str | None]] = {}
_last_good: dict[str, str | None] = {}  # último valor que el servidor confirmó, por raíz


def _warn(message: str) -> None:
    print(f"[higpertext-mcp/repository_resolution] {message}", file=sys.stderr)


def host_id() -> str:
    """Identificador de esta máquina: HIGPERTEXT_HOST_ID, o ~/.config/higpertext/
    host_id si existe, o "local" (el mismo valor por defecto del servidor)."""
    explicit = os.environ.get("HIGPERTEXT_HOST_ID", "").strip()
    if explicit:
        return explicit
    try:
        value = (Path.home() / ".config" / "higpertext" / "host_id").read_text(encoding="utf-8").strip()
        if value:
            return value
    except OSError:
        pass
    return "local"


def git_remote(root: Path) -> str:
    """URL de `[remote "origin"]` en <root>/.git/config, sin ejecutar git. "" si no
    hay (repo sin remote, no es un repo, o worktree con .git como archivo)."""
    try:
        text = (root / ".git" / "config").read_text(encoding="utf-8")
    except OSError:
        return ""
    in_origin = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("["):
            in_origin = line == '[remote "origin"]'
            continue
        if in_origin and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() == "url":
                return value.strip()
    return ""


def invalidate(root: Path | None = None) -> None:
    """Descarta lo cacheado (de una raíz o de todas)."""
    if root is None:
        _cache.clear()
        _last_good.clear()
    else:
        _cache.pop(str(root), None)


def invalidate_cache_only(root: Path) -> None:
    """Expira la caché de TTL de una raíz sin olvidar el último valor bueno (para pruebas
    y para forzar una relectura que, si falla, conserva lo ya confirmado)."""
    _cache.pop(str(root), None)


async def server_profile(root: Path) -> str | None:
    """Perfil activo según el servidor, o None (sin perfil allí, servidor caído, o
    HIGPERTEXT_PROFILE_SOURCE=local)."""
    if config.profile_source() == "local":
        return None
    key = str(root)
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return hit[1]
    try:
        repo = await profile_client.resolve_repository(str(root), git_remote(root), host_id())
        cfg = await profile_client.get_repository_config(repo["id"])
        profile = (cfg.get("profile") or "").strip() or None
    except Exception as exc:  # noqa: BLE001 — cualquier fallo de red/servidor
        _warn(f"sin perfil del servidor para {root}: {profile_client.describe_error(exc)}")
        stale = _last_good.get(key)  # un fallo momentáneo no debe dejar al agente sin perfil
        _cache[key] = (now + _NEGATIVE_TTL_S, stale)
        return stale
    _cache[key] = (now + _TTL_S, profile)
    _last_good[key] = profile
    return profile


async def adopt_legacy_profile(root: Path, legacy_profile: str) -> str | None:
    """El repositorio no tiene perfil en el servidor y hay uno en environment.json:
    se copia al servidor (una sola vez) y se devuelve. Si otro lo fijó mientras
    tanto, gana el del servidor. Con el servidor caído devuelve None: no se usa un
    valor que el servidor no ha confirmado."""
    result = await sync_profile(root, legacy_profile)
    if result["status"] in ("set", "unchanged"):
        return result["profile"]
    if result["status"] == "kept":
        return result["profile"]
    return None


async def sync_profile(root: Path, profile: str, *, replace: bool = False) -> dict:
    """Refleja en el servidor el perfil elegido para `root`.

    - el repositorio no tenía perfil en el servidor → se guarda (`set`);
    - ya tenía otro y `replace` → se reemplaza (`replaced`);
    - ya tenía otro y no `replace` → el servidor gana y se informa (`kept`);
    - ya era el mismo → `unchanged`.
    Nunca lanza: un servidor caído devuelve `unreachable`.
    """
    profile = profile.strip()
    if config.profile_source() == "local":
        return {"status": "skipped", "reason": "HIGPERTEXT_PROFILE_SOURCE=local: solo se usa environment.json"}
    try:
        repo = await profile_client.resolve_repository(str(root), git_remote(root), host_id())
        cfg = await profile_client.get_repository_config(repo["id"])
        current = (cfg.get("profile") or "").strip()
        if current == profile:
            return {"status": "unchanged", "profile": profile, "repository_id": repo["id"]}
        if current and not replace:
            return {"status": "kept", "profile": current, "requested": profile, "repository_id": repo["id"]}
        await profile_client.set_repository_config(repo["id"], profile, cfg.get("overrides") or {})
        result = {"status": "replaced" if current else "set", "profile": profile, "repository_id": repo["id"]}
        if current:
            result["previous"] = current
        return result
    except Exception as exc:  # noqa: BLE001
        return {"status": "unreachable", "error": profile_client.describe_error(exc)}
    finally:
        invalidate(root)
