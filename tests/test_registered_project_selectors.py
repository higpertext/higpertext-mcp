"""RFC-0020 fase 4: el repositorio es la unidad; root_path acepta carpetas dentro de un
checkout y repository_id elige el checkout de este host (por binding)."""

import jsonschema
import pytest

from higpertext_mcp import discovery, server

pytestmark = pytest.mark.anyio


def project_with(tmp_path, *names, project_id="proj-1"):
    roots = [tmp_path / n for n in names]
    for r in roots:
        r.mkdir(parents=True, exist_ok=True)
    return {"id": project_id, "name": "higpertext", "root_path": str(roots[0]), "paths": [str(r) for r in roots]}


@pytest.fixture
def resolve_to(monkeypatch):
    def install(project):
        async def fake(root_path):
            return project

        monkeypatch.setattr(discovery.profile_client, "resolve_project", fake)

    return install


async def test_a_subfolder_resolves_to_the_registered_checkout_that_contains_it(tmp_path, resolve_to):
    project = project_with(tmp_path, "repo")
    resolve_to(project)
    sub = tmp_path / "repo" / "src" / "app" / "pages"
    sub.mkdir(parents=True)
    root, resolved = await discovery.resolve_registered_project(root_path=str(sub))
    assert root == (tmp_path / "repo").resolve()  # el checkout, no la subcarpeta
    assert resolved["id"] == "proj-1"


async def test_the_deepest_registered_checkout_wins_when_they_are_nested(tmp_path, resolve_to):
    project = project_with(tmp_path, "mono", "mono/packages/api")
    resolve_to(project)
    inner = tmp_path / "mono" / "packages" / "api" / "src"
    inner.mkdir(parents=True)
    root, _ = await discovery.resolve_registered_project(root_path=str(inner))
    assert root == (tmp_path / "mono" / "packages" / "api").resolve()


async def test_a_path_outside_every_checkout_is_still_rejected(tmp_path, resolve_to):
    resolve_to(project_with(tmp_path, "repo"))
    elsewhere = tmp_path / "otro"
    elsewhere.mkdir()
    with pytest.raises(ValueError, match="no pertenece al proyecto"):
        await discovery.resolve_registered_project(root_path=str(elsewhere))


async def test_a_sibling_with_a_common_prefix_is_not_inside_the_checkout(tmp_path, resolve_to):
    resolve_to(project_with(tmp_path, "repo"))
    sibling = tmp_path / "repo-extra"
    sibling.mkdir()
    with pytest.raises(ValueError, match="no pertenece al proyecto"):
        await discovery.resolve_registered_project(root_path=str(sibling))


def install_repos(monkeypatch, tmp_path, *, checkouts, project=None, repo_id="repo-1"):
    project = project or project_with(tmp_path, "repo")

    async def list_repositories(project_id=""):
        return [{"id": repo_id, "project_id": project["id"], "name": "repo", "remote": "", "checkouts": checkouts}]

    async def list_projects():
        return [project]

    monkeypatch.setattr(discovery.profile_client, "list_repositories", list_repositories)
    monkeypatch.setattr(discovery.profile_client, "list_projects", list_projects)
    return project


async def test_repository_id_resolves_to_the_checkout_of_this_host(tmp_path, monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_HOST_ID", "host-a")
    mine, theirs = tmp_path / "repo", tmp_path / "en-otra-maquina"
    mine.mkdir()
    install_repos(monkeypatch, tmp_path, checkouts=[
        {"host_id": "host-b", "path": str(theirs)}, {"host_id": "host-a", "path": str(mine)},
    ])
    root, project = await discovery.resolve_registered_project(repository_id="repo-1")
    assert root == mine.resolve() and project["id"] == "proj-1"


async def test_repository_id_without_a_checkout_in_this_host_explains_which_hosts_have_one(tmp_path, monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_HOST_ID", "host-a")
    install_repos(monkeypatch, tmp_path, checkouts=[{"host_id": "host-b", "path": "/x"}])
    with pytest.raises(ValueError, match=r"no tiene checkout en este host \(host-a\).*host-b"):
        await discovery.resolve_registered_project(repository_id="repo-1")


async def test_unknown_repository_and_vanished_project(tmp_path, monkeypatch):
    monkeypatch.setenv("HIGPERTEXT_HOST_ID", "host-a")
    install_repos(monkeypatch, tmp_path, checkouts=[{"host_id": "host-a", "path": str(tmp_path)}])
    with pytest.raises(ValueError, match="repositorio registrado no encontrado"):
        await discovery.resolve_registered_project(repository_id="otro")

    async def no_projects():
        return []

    monkeypatch.setattr(discovery.profile_client, "list_projects", no_projects)
    with pytest.raises(ValueError, match="ya no existe"):
        await discovery.resolve_registered_project(repository_id="repo-1")


async def test_selectors_are_mutually_exclusive_and_one_is_required():
    for kwargs in ({"root_path": "/a", "repository_id": "r"}, {"project_id": "p", "repository_id": "r"}, {"root_path": "/a", "project_id": "p"}):
        with pytest.raises(ValueError, match="mutuamente excluyentes"):
            await discovery.resolve_registered_project(**kwargs)
    with pytest.raises(ValueError, match="repository_id"):
        await discovery.resolve_registered_project()


def test_render_adapters_accepts_repository_id_as_the_only_selector():
    schema = server._RENDER_ADAPTERS_TOOL.inputSchema
    jsonschema.validate({"repository_id": "repo-1"}, schema)
    jsonschema.validate({"repository_id": "repo-1", "assistants": ["claude"]}, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"assistants": ["claude"]}, schema)  # sin ningún selector
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"repository_id": "r", "root_path": "/x"}, schema)  # oneOf: exactamente uno


def test_configure_and_overview_tools_expose_repository_id():
    for tool in (server._CONFIGURE_TOOL, server._SYSTEM_OVERVIEW_TOOL):
        assert "repository_id" in tool.inputSchema["properties"]
    jsonschema.validate({"profile": "p", "repository_id": "r"}, server._CONFIGURE_TOOL.inputSchema)
