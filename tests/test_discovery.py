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
