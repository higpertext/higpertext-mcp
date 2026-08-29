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


def test_intersects_profile_with_real_capabilities():
    root = _make_project(
        active_profile="dev",
        capabilities=["common.grep-search", "git.diff", "common.unrelated-thing"],
    )
    result = discovery.allowed_capability_ids(root)
    assert result == sorted(["common.grep-search", "git.diff"])


def test_profile_without_matching_capabilities_returns_empty():
    root = _make_project(active_profile="dev", capabilities=["common.unrelated-thing"])
    assert discovery.allowed_capability_ids(root) == []


def test_profile_grants_arbitrary_capabilities_beyond_old_fixed_ten():
    """Cobertura completa: cualquier capability real del motor que el perfil otorgue
    debe quedar expuesta, no solo la vieja lista fija de 10 (ver discovery.py)."""
    engine_ids = discovery.list_all_capability_ids()
    assert len(engine_ids) > 10, "el motor debería tener más de 10 capabilities reales"
    granted = engine_ids[:15]
    root = _make_project(active_profile="dev", capabilities=granted)
    assert discovery.allowed_capability_ids(root) == sorted(granted)


def test_project_root_override_env(monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", "/tmp/somewhere")
    assert discovery.resolve_project_root() == Path("/tmp/somewhere").resolve()
