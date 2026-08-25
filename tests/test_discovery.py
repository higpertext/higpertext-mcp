import json
import tempfile
from pathlib import Path

from higpertext_mcp import discovery


def _make_project(active_profile: str | None, capabilities: list[str]) -> Path:
    root = Path(tempfile.mkdtemp())
    config_dir = root / ".higpertext" / "config"
    config_dir.mkdir(parents=True)
    if active_profile is not None:
        (config_dir / "environment.json").write_text(
            json.dumps({"active_profile": active_profile}), encoding="utf-8"
        )
    profiles_dir = root / "src" / "config" / "profiles"
    profiles_dir.mkdir(parents=True)
    if active_profile is not None:
        (profiles_dir / f"{active_profile}.json").write_text(
            json.dumps({"capabilities": capabilities}), encoding="utf-8"
        )
    return root


def test_no_active_profile_returns_empty():
    root = _make_project(active_profile=None, capabilities=[])
    assert discovery.allowed_capability_ids(root) == []


def test_intersects_profile_with_v1_set():
    root = _make_project(
        active_profile="dev",
        capabilities=["common.grep-search", "git.diff", "common.unrelated-thing"],
    )
    result = discovery.allowed_capability_ids(root)
    assert result == sorted(["common.grep-search", "git.diff"])


def test_profile_without_matching_v1_capabilities_returns_empty():
    root = _make_project(active_profile="dev", capabilities=["common.unrelated-thing"])
    assert discovery.allowed_capability_ids(root) == []


def test_all_v1_ids_granted_returns_full_set():
    root = _make_project(
        active_profile="dev", capabilities=list(discovery.V1_CAPABILITY_IDS)
    )
    assert set(discovery.allowed_capability_ids(root)) == discovery.V1_CAPABILITY_IDS


def test_project_root_override_env(monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", "/tmp/somewhere")
    assert discovery.resolve_project_root() == Path("/tmp/somewhere").resolve()
