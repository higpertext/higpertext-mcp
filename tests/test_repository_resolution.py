"""RFC-0020 fase 3: el perfil activo viene del servidor y environment.json es el respaldo."""

import json

import pytest

from higpertext_mcp import config, discovery, project_config, repository_resolution

pytestmark = pytest.mark.anyio


class FakeServer:
    """Simula profile_client: un repositorio por ruta y su RepositoryConfig."""

    def __init__(self, profile="", down=False):
        self.profile = profile
        self.overrides = {"assistant": "claude"}
        self.down = down
        self.resolved = []  # (path, remote, host_id)
        self.set_calls = []

    async def resolve_repository(self, path, remote="", host_id=""):
        if self.down:
            raise ConnectionError("profile server caído")
        self.resolved.append((path, remote, host_id))
        return {"id": "repo-1", "project_id": "proj-1", "name": "x", "remote": remote, "checkouts": [], "match": "new", "created": False}

    async def get_repository_config(self, repository_id):
        if self.down:
            raise ConnectionError("profile server caído")
        return {"repository_id": repository_id, "profile": self.profile, "overrides": dict(self.overrides)}

    async def set_repository_config(self, repository_id, profile, overrides=None):
        self.set_calls.append((repository_id, profile, dict(overrides or {})))
        self.profile = profile
        return {"repository_id": repository_id, "profile": profile, "overrides": dict(overrides or {})}


@pytest.fixture
def server(monkeypatch):
    monkeypatch.delenv("HIGPERTEXT_PROFILE_SOURCE", raising=False)  # reactiva el camino del servidor
    fake = FakeServer()
    monkeypatch.setattr(repository_resolution.profile_client, "resolve_repository", fake.resolve_repository)
    monkeypatch.setattr(repository_resolution.profile_client, "get_repository_config", fake.get_repository_config)
    monkeypatch.setattr(repository_resolution.profile_client, "set_repository_config", fake.set_repository_config)
    return fake


def write_env(root, profile):
    cfg = root / ".higpertext" / "config"
    cfg.mkdir(parents=True)
    (cfg / "environment.json").write_text(json.dumps({"active_profile": profile}))


def write_env_again(root, profile):
    (root / ".higpertext" / "config" / "environment.json").write_text(json.dumps({"active_profile": profile}))


async def test_the_server_profile_wins_over_environment_json(tmp_path, server):
    write_env(tmp_path, "viejo_local")
    server.profile = "del_servidor"
    assert await discovery.effective_profile(tmp_path) == "del_servidor"


async def test_environment_json_is_adopted_once_when_the_repo_has_no_server_profile(tmp_path, server):
    write_env(tmp_path, "solo_local")
    server.profile = ""
    assert await discovery.effective_profile(tmp_path) == "solo_local"
    assert server.profile == "solo_local" and len(server.set_calls) == 1  # se copió al servidor

    # Desde entonces manda el servidor: cambiar el archivo ya no cambia nada.
    write_env_again(tmp_path, "cambiado_a_mano")
    repository_resolution.invalidate(tmp_path)
    assert await discovery.effective_profile(tmp_path) == "solo_local"
    assert len(server.set_calls) == 1


async def test_with_the_server_down_there_is_no_profile_not_a_guess_from_the_file(tmp_path, server):
    write_env(tmp_path, "solo_local")
    server.down = True
    assert await discovery.effective_profile(tmp_path) is None


async def test_the_last_confirmed_profile_survives_a_momentary_server_failure(tmp_path, server):
    server.profile = "del_servidor"
    assert await discovery.effective_profile(tmp_path) == "del_servidor"
    repository_resolution.invalidate_cache_only(tmp_path)  # expira la caché pero conserva el último valor bueno
    server.down = True
    assert await discovery.effective_profile(tmp_path) == "del_servidor"


async def test_a_server_that_never_answered_has_no_last_good_value(tmp_path, server):
    server.down = True
    assert await discovery.effective_profile(tmp_path) is None


async def test_deleting_environment_json_does_not_change_what_the_agent_sees(tmp_path, server):
    server.profile = "del_servidor"
    assert await discovery.effective_profile(tmp_path) == "del_servidor"  # no hay archivo local


async def test_no_profile_anywhere_is_none(tmp_path, server):
    assert await discovery.effective_profile(tmp_path) is None


async def test_local_source_never_calls_the_server(tmp_path, server, monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_PROFILE_SOURCE", "local")
    write_env(tmp_path, "solo_local")
    server.profile = "del_servidor"
    assert await discovery.effective_profile(tmp_path) == "solo_local"
    assert server.resolved == []


async def test_responses_are_cached_and_failures_are_not_retried_every_call(tmp_path, server):
    server.profile = "p"
    await discovery.effective_profile(tmp_path)
    await discovery.effective_profile(tmp_path)
    assert len(server.resolved) == 1
    repository_resolution.invalidate(tmp_path)
    await discovery.effective_profile(tmp_path)
    assert len(server.resolved) == 2

    other = tmp_path / "otro"
    other.mkdir()
    server.down = True
    await discovery.effective_profile(other)
    server.down = False
    await discovery.effective_profile(other)  # dentro del TTL negativo: no vuelve a intentar
    assert server.resolved.count((str(other), "", "local")) == 0


async def test_the_remote_and_host_are_sent_to_the_server(tmp_path, server, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text('[core]\n\tbare = false\n[remote "upstream"]\n\turl = https://x/y.git\n[remote "origin"]\n\turl = git@github.com:org/repo.git\n')
    monkeypatch.setenv("HIGPERTEXT_HOST_ID", "host-a")
    await discovery.effective_profile(tmp_path)
    assert server.resolved == [(str(tmp_path), "git@github.com:org/repo.git", "host-a")]


def test_git_remote_handles_missing_files_and_repos_without_origin(tmp_path):
    assert repository_resolution.git_remote(tmp_path) == ""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]\n\tbare = false\n")
    assert repository_resolution.git_remote(tmp_path) == ""


def test_host_id_prefers_the_environment_then_the_config_file_then_local(tmp_path, monkeypatch):
    monkeypatch.delenv("HIGPERTEXT_HOST_ID", raising=False)
    monkeypatch.setattr(repository_resolution.Path, "home", lambda: tmp_path)
    assert repository_resolution.host_id() == "local"
    (tmp_path / ".config" / "higpertext").mkdir(parents=True)
    (tmp_path / ".config" / "higpertext" / "host_id").write_text("uuid-1234\n")
    assert repository_resolution.host_id() == "uuid-1234"
    monkeypatch.setenv("HIGPERTEXT_HOST_ID", "docker-host")
    assert repository_resolution.host_id() == "docker-host"


def test_profile_source_defaults_to_the_server(monkeypatch):
    monkeypatch.delenv("HIGPERTEXT_PROFILE_SOURCE", raising=False)
    assert config.profile_source() == "server"
    monkeypatch.setenv("HIGPERTEXT_PROFILE_SOURCE", "LOCAL")
    assert config.profile_source() == "local"


async def test_sync_profile_sets_it_when_the_server_has_none(tmp_path, server):
    result = await repository_resolution.sync_profile(tmp_path, "software_developer")
    assert result["status"] == "set" and server.profile == "software_developer"
    assert server.set_calls[0][2] == {"assistant": "claude"}  # conserva los overrides


async def test_sync_profile_keeps_the_server_value_unless_replace_is_requested(tmp_path, server):
    server.profile = "del_servidor"
    kept = await repository_resolution.sync_profile(tmp_path, "otro")
    assert kept == {"status": "kept", "profile": "del_servidor", "requested": "otro", "repository_id": "repo-1"}
    assert server.set_calls == []

    replaced = await repository_resolution.sync_profile(tmp_path, "otro", replace=True)
    assert replaced["status"] == "replaced" and replaced["previous"] == "del_servidor" and server.profile == "otro"

    assert (await repository_resolution.sync_profile(tmp_path, "otro"))["status"] == "unchanged"


async def test_sync_profile_never_raises_when_the_server_is_down(tmp_path, server):
    server.down = True
    result = await repository_resolution.sync_profile(tmp_path, "x")
    assert result["status"] == "unreachable" and "error" in result


async def test_a_synced_change_is_visible_immediately(tmp_path, server):
    server.profile = "uno"
    assert await discovery.effective_profile(tmp_path) == "uno"
    await repository_resolution.sync_profile(tmp_path, "dos", replace=True)  # invalida la caché
    assert await discovery.effective_profile(tmp_path) == "dos"


def test_replace_profile_updates_the_local_mirror_only_when_asked(tmp_path):
    write_env(tmp_path, "actual")
    project_config.create_project_configuration(tmp_path, "nuevo")
    assert json.loads((tmp_path / ".higpertext/config/environment.json").read_text())["active_profile"] == "actual"
    project_config.create_project_configuration(tmp_path, "nuevo", replace_profile=True)
    assert json.loads((tmp_path / ".higpertext/config/environment.json").read_text())["active_profile"] == "nuevo"


async def test_sync_profile_is_skipped_with_the_local_source_and_never_reaches_the_server(tmp_path, server, monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_PROFILE_SOURCE", "local")
    result = await repository_resolution.sync_profile(tmp_path, "x", replace=True)
    assert result["status"] == "skipped"
    assert server.resolved == [] and server.set_calls == []


async def test_adoption_loses_to_a_profile_another_process_set_first(tmp_path, server, monkeypatch):
    write_env(tmp_path, "mio")
    server.profile = ""
    original = repository_resolution.profile_client.get_repository_config
    calls = {"n": 0}

    async def racing(repository_id):
        calls["n"] += 1
        if calls["n"] == 2:  # entre la lectura y la adopción, otro proceso fija su perfil
            server.profile = "del_otro"
        return await original(repository_id)

    monkeypatch.setattr(repository_resolution.profile_client, "get_repository_config", racing)
    assert await discovery.effective_profile(tmp_path) == "del_otro"


async def test_an_unregistered_project_is_a_quiet_no_profile_not_a_warning(tmp_path, server, monkeypatch, capsys):
    """El servidor ya no crea proyectos al resolver: un directorio temporal de pruebas
    responde 'no registrado'. Es un caso normal: sin perfil del servidor y sin ruido."""

    async def not_registered(path, remote="", host_id=""):
        raise repository_resolution.profile_client.ProjectNotRegisteredError(path)

    monkeypatch.setattr(repository_resolution.profile_client, "resolve_repository", not_registered)
    repository_resolution.invalidate(tmp_path)

    assert await repository_resolution.server_profile(tmp_path) is None
    assert "sin perfil del servidor" not in capsys.readouterr().err


async def test_sync_profile_reports_unregistered_instead_of_unreachable(tmp_path, server, monkeypatch):
    async def not_registered(path, remote="", host_id=""):
        raise repository_resolution.profile_client.ProjectNotRegisteredError(path)

    monkeypatch.setattr(repository_resolution.profile_client, "resolve_repository", not_registered)
    result = await repository_resolution.sync_profile(tmp_path, "dev")

    assert result["status"] == "unregistered"
    assert "no está registrado" in result["error"]
    assert server.set_calls == []


async def test_an_unregistered_remote_is_not_registered_not_unreachable(tmp_path, server, monkeypatch, capsys):
    """Un clon con remote que ningún repositorio registrado posee: el servidor responde NOT_FOUND
    por remote. Debe verse como «no registrado» (sin ruido ni 'unreachable')."""
    import grpc

    class NotFound(grpc.aio.AioRpcError):
        def __init__(self):
            pass

        def code(self):
            return grpc.StatusCode.NOT_FOUND

    async def by_remote(remote):
        raise NotFound()

    monkeypatch.setattr(repository_resolution, "git_remote", lambda root: "https://github.com/org/temporal.git")
    monkeypatch.setattr(repository_resolution.profile_client, "resolve_repository_by_remote", by_remote)
    repository_resolution.invalidate(tmp_path)

    assert await repository_resolution.server_profile(tmp_path) is None
    assert "sin perfil del servidor" not in capsys.readouterr().err
    assert (await repository_resolution.sync_profile(tmp_path, "dev"))["status"] == "unregistered"
