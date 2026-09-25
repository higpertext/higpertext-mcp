import json
import tempfile
from pathlib import Path

import pytest

from higpertext_mcp import discovery
from higpertext_mcp.gen.profile.v1 import profile_pb2


def _make_project(active_profile: str | None) -> Path:
    root = Path(tempfile.mkdtemp())
    config_dir = root / ".higpertext" / "config"
    config_dir.mkdir(parents=True)
    if active_profile is not None:
        (config_dir / "environment.json").write_text(
            json.dumps({"active_profile": active_profile}), encoding="utf-8"
        )
    return root


@pytest.mark.anyio
async def test_no_active_profile_passes_none_through_fail_closed():
    """Sin perfil activo, discovery.py delega igual a profile_client (que es
    quien decide fail-closed sobre `profile` vacío/None — ver profile_client.py)."""
    root = _make_project(active_profile=None)
    assert await discovery.allowed_capabilities(root) == []


@pytest.mark.anyio
async def test_delegates_active_profile_to_profile_client(monkeypatch):
    seen_profiles: list[str | None] = []
    caps = [profile_pb2.Capability(id="common.grep-search"), profile_pb2.Capability(id="git.diff")]

    async def fake_list_allowed(profile):
        seen_profiles.append(profile)
        return caps

    monkeypatch.setattr(discovery.profile_client, "list_allowed_capabilities", fake_list_allowed)

    root = _make_project(active_profile="dev")
    result = await discovery.allowed_capabilities(root)

    assert seen_profiles == ["dev"]
    assert result == caps


@pytest.mark.anyio
async def test_profile_client_failure_is_fail_closed(monkeypatch):
    async def fake_list_allowed(profile):
        return []

    monkeypatch.setattr(discovery.profile_client, "list_allowed_capabilities", fake_list_allowed)

    root = _make_project(active_profile="dev")
    assert await discovery.allowed_capabilities(root) == []


def test_project_root_override_env(monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", "/tmp/somewhere")
    assert discovery.resolve_project_root() == Path("/tmp/somewhere").resolve()


def test_project_path_mapping_between_container_and_host(monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", "/workspace")
    monkeypatch.setenv("HIGPERTEXT_HOST_PROJECT_ROOT", "/host/projects/server")
    monkeypatch.setenv("HIGPERTEXT_HOST_PROJECTS_ROOT", "/host/projects")
    monkeypatch.setenv("HIGPERTEXT_PROJECTS_MOUNT", "/projects")

    assert discovery.canonical_project_path(Path("/workspace")) == Path("/host/projects/server")
    assert discovery.canonical_project_path(Path("/projects/frontend")) == Path("/host/projects/frontend")
    assert discovery.local_project_path("/host/projects/frontend") == Path("/projects/frontend")


def test_allowed_project_roots_reject_outside_path(monkeypatch, tmp_path):
    allowed = tmp_path / "projects"
    allowed.mkdir()
    monkeypatch.setenv("HIGPERTEXT_ALLOWED_PROJECT_ROOTS", str(allowed))

    assert discovery.canonical_project_path(allowed / "app") == (allowed / "app").resolve()
    with pytest.raises(ValueError, match="raíces autorizadas"):
        discovery.canonical_project_path(tmp_path / "private")


def test_project_root_override_respects_allowed_roots(monkeypatch, tmp_path):
    allowed = tmp_path / "projects"
    allowed.mkdir()
    monkeypatch.setenv("HIGPERTEXT_ALLOWED_PROJECT_ROOTS", str(allowed))
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(tmp_path / "private"))

    with pytest.raises(ValueError, match="raíces autorizadas"):
        discovery.resolve_project_root()


@pytest.mark.anyio
async def test_resolve_registered_project_accepts_any_registered_path(monkeypatch, tmp_path):
    registered_roots = [tmp_path / name for name in ("server", "frontend", "docs", "infra", "deploy")]
    project_root, frontend_root = registered_roots[:2]
    project = {
        "id": "ebaf208b-de59-412b-b50f-cc87cce41ffc",
        "root_path": str(project_root),
        "paths": [str(path) for path in registered_roots],
    }

    async def fake_resolve_project(root_path):
        assert root_path == str(registered_roots[-1].resolve())
        return project

    monkeypatch.setattr(discovery.profile_client, "resolve_project", fake_resolve_project)

    root, resolved = await discovery.resolve_registered_project(root_path=str(registered_roots[-1]))

    assert root == registered_roots[-1].resolve()
    assert resolved["id"] == project["id"]


@pytest.mark.anyio
async def test_resolve_registered_project_by_id_uses_registered_primary_root(monkeypatch, tmp_path):
    project_root = tmp_path / "server"
    project = {"id": "project-1", "root_path": str(project_root), "paths": [str(project_root)]}

    async def fake_list_projects():
        return [project]

    monkeypatch.setattr(discovery.profile_client, "list_projects", fake_list_projects)

    root, resolved = await discovery.resolve_registered_project(project_id="project-1")

    assert root == project_root.resolve()
    assert resolved == project


@pytest.mark.anyio
async def test_resolve_registered_project_by_id_respects_allowed_roots(monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    monkeypatch.setenv("HIGPERTEXT_ALLOWED_PROJECT_ROOTS", str(allowed))

    async def fake_list_projects():
        return [{"id": "project-1", "root_path": str(outside)}]

    monkeypatch.setattr(discovery.profile_client, "list_projects", fake_list_projects)

    with pytest.raises(ValueError, match="raíces autorizadas"):
        await discovery.resolve_registered_project(project_id="project-1")
