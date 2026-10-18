"""Carga y registra el manifiesto portable del proyecto."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import grpc
import yaml

from higpertext_mcp import profile_client, repository_resolution


class ProjectManifestError(ValueError):
    """El manifiesto o su asociación al Project registrado no es válida."""


def _normal_remote(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if "://" in raw:
        parsed = urlparse(raw)
        host, path = parsed.hostname or "", parsed.path
    elif ":" in raw and "/" not in raw.split(":", 1)[0]:
        host, path = raw.split(":", 1)
        host = host.rsplit("@", 1)[-1]
    else:
        return ""
    path = path.strip().strip("/").lower()
    if path.endswith(".git"):
        path = path[:-4]
    host = host.strip().lower()
    return f"{host}/{path}" if host and path else ""


def load_manifest(root: Path) -> tuple[Path, dict]:
    """Busca el manifiesto en root o sus ancestros y valida el formato v1."""
    root = root.expanduser().resolve()
    for directory in (root, *root.parents):
        path = directory / ".higpertext" / "project.yaml"
        if not path.is_file():
            continue
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ProjectManifestError(f"{path}: YAML inválido: {exc}") from exc
        if not isinstance(value, dict) or set(value) - {"version", "project", "organization", "repositories"}:
            raise ProjectManifestError(f"{path}: campos raíz inválidos")
        if value.get("version") != 1:
            raise ProjectManifestError(f"{path}: version debe ser 1")
        project = value.get("project")
        organization = value.get("organization")
        if organization is not None:
            if not isinstance(organization, dict) or set(organization) != {"id"}:
                raise ProjectManifestError(f"{path}: organization debe tener solo id")
            if not isinstance(organization.get("id"), str) or not organization["id"].strip():
                raise ProjectManifestError(f"{path}: organization.id debe ser texto no vacío")
            organization["id"] = organization["id"].strip()
        repositories = value.get("repositories")
        if not isinstance(project, dict) or set(project) - {"id", "name"}:
            raise ProjectManifestError(f"{path}: project debe tener solo id y name")
        if not isinstance(project.get("name"), str) or not project["name"].strip():
            raise ProjectManifestError(f"{path}: project.name es obligatorio")
        if project.get("id") is not None and not isinstance(project["id"], str):
            raise ProjectManifestError(f"{path}: project.id debe ser texto")
        if not isinstance(repositories, list) or not repositories:
            raise ProjectManifestError(f"{path}: repositories debe ser una lista no vacía")
        names, remotes = set(), set()
        for index, repository in enumerate(repositories):
            if not isinstance(repository, dict) or set(repository) != {"name", "remote"}:
                raise ProjectManifestError(f"{path}: repositories[{index}] debe tener name y remote")
            name, remote = repository["name"], repository["remote"]
            if not isinstance(name, str) or not name.strip() or name.strip() in names:
                raise ProjectManifestError(f"{path}: nombre vacío o repetido en repositories[{index}]")
            name = name.strip()
            repository["name"] = name
            normalized = _normal_remote(remote) if isinstance(remote, str) else ""
            if not normalized or normalized in remotes:
                raise ProjectManifestError(f"{path}: remote inválido o repetido en repositories[{index}]")
            names.add(name)
            remotes.add(normalized)
        return path, value
    raise ProjectManifestError(f"no se encontró .higpertext/project.yaml desde {root}")


async def register_manifest(root: Path, organization_id: str, authorized_project_id: str = "") -> dict:
    """Registra remotes de forma idempotente y enlaza el checkout actual.

    Operación explícita de onboarding. La resolución habitual de sesiones
    nunca crea Projects ni Repositories automáticamente.
    """
    root = root.expanduser().resolve()
    path, manifest = load_manifest(root)
    organization_id = organization_id.strip()
    declared_organization_id = (manifest.get("organization") or {}).get("id", "")
    if not organization_id or (declared_organization_id and declared_organization_id != organization_id):
        raise ProjectManifestError("organization.id debe coincidir con organization_id autorizado en la llamada MCP")
    authorized_project_id = authorized_project_id.strip()
    local_remote = repository_resolution.git_remote(root)
    local_key = _normal_remote(local_remote)
    entries = manifest["repositories"]
    current = next((item for item in entries if _normal_remote(item["remote"]) == local_key), None)
    if not local_key or current is None:
        raise ProjectManifestError(f"el remote origin actual no está declarado en {path}")

    project_id = (manifest["project"].get("id") or "").strip()
    if project_id:
        if authorized_project_id != project_id:
            raise ProjectManifestError("para registrar un Project existente, envía su project_id para validar el permiso del token")
        projects = await profile_client.list_projects()
        if not any(item["id"] == project_id for item in projects):
            raise ProjectManifestError(f"project.id {project_id!r} no existe en ProjectService")

    existing_project_ids = set()
    for item in entries:
        try:
            identity = await profile_client.resolve_repository_by_remote(item["remote"])
        except grpc.aio.AioRpcError as exc:
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                continue
            raise
        existing_project_ids.add(identity["project_id"])

    if project_id:
        if any(existing_id != project_id for existing_id in existing_project_ids):
            raise ProjectManifestError("los remotes declarados no pertenecen todos al project.id indicado")
    else:
        if len(existing_project_ids) > 1:
            raise ProjectManifestError("los remotes declarados ya pertenecen a Projects distintos")
        if existing_project_ids:
            project_id = next(iter(existing_project_ids))
            if authorized_project_id != project_id:
                raise ProjectManifestError(f"este remote ya pertenece al Project {project_id}; envía ese project_id para validar el permiso del token")
        else:
            created = await profile_client.register_project(str(root), organization_id)
            project_id = created["id"]

    registered = []
    for item in entries:
        result = await profile_client.register_repository(project_id, item["name"], item["remote"])
        registered.append({"name": item["name"], "repository_id": result["id"], "created": result["created"]})

    checkout = await profile_client.resolve_repository(
        str(root), local_remote, repository_resolution.host_id()
    )

    if manifest["project"].get("id") != project_id or declared_organization_id != organization_id:
        manifest["project"]["id"] = project_id
        manifest["organization"] = {"id": organization_id}
        original_mode = stat.S_IMODE(path.stat().st_mode)
        fd, temporary = tempfile.mkstemp(prefix=".project-", suffix=".yaml", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                yaml.safe_dump(manifest, stream, sort_keys=False, allow_unicode=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, original_mode)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    return {
        "manifest": str(path),
        "project_id": project_id,
        "repositories": registered,
        "checkout": checkout,
    }
