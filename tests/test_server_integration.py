"""Valida el wire protocol real (no solo las funciones internas): levanta el
Server en memoria y lo habla con un ClientSession de verdad, como haría un
cliente MCP real (Claude Code u otro).

El catálogo de capabilities ya no viene de perfiles JSON locales sino del
profile server (gRPC) — acá se stubea `discovery.profile_client` en vez de
levantar un profile server real, mismo criterio que `ExternalServerPool.
from_sessions` usa para no depender de red real en tests."""

import json
import tempfile
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from higpertext_mcp import adapter_renderer, discovery, dispatch, hook_renderer, skill_renderer, server as server_module
from higpertext_mcp.gen.profile.v1 import profile_pb2


def _make_project(active_profile: str) -> Path:
    root = Path(tempfile.mkdtemp())
    config_dir = root / ".higpertext" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "environment.json").write_text(
        json.dumps({"active_profile": active_profile}), encoding="utf-8"
    )
    return root


_GREP_SEARCH = profile_pb2.Capability(
    id="common.grep-search",
    entrypoint="capabilities/common/scripts/core/search/grep_search.py",
    language="python",
    parameters=[profile_pb2.Parameter(name="pattern", required=False)],
)
_GIT_DIFF = profile_pb2.Capability(
    id="git.diff", entrypoint="capabilities/git/scripts/git_diff.py", language="python"
)


def _stub_profile_catalog(
    monkeypatch, profile_to_capabilities: dict[str, list[profile_pb2.Capability]]
) -> None:
    async def fake_list_allowed(profile):
        return profile_to_capabilities.get(profile, [])

    monkeypatch.setattr(discovery.profile_client, "list_allowed_capabilities", fake_list_allowed)


@pytest.mark.anyio
async def test_list_tools_over_real_protocol(monkeypatch):
    root = _make_project("dev")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))
    _stub_profile_catalog(monkeypatch, {"dev": [_GREP_SEARCH, _GIT_DIFF]})

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_tools()
        names = {t.name for t in result.tools}
        assert names == {"higpertext-configure-project", "higpertext-render-adapters", "higpertext-governance-rule", "higpertext-governance-exception", "higpertext-profile", "higpertext-capability", "higpertext-hook-admin", "higpertext-skill", "common-grep-search", "git-diff"}
        grep_tool = next(t for t in result.tools if t.name == "common-grep-search")
        assert grep_tool.annotations.readOnlyHint is True
        assert "pattern" in grep_tool.inputSchema["properties"]


def test_render_adapters_requires_project_selector_but_accepts_either_form():
    schema = server_module._RENDER_ADAPTERS_TOOL.inputSchema

    assert schema["oneOf"] == [{"required": ["project_id"]}, {"required": ["root_path"]}]
    assert "required" not in schema


def test_configure_project_accepts_project_selector():
    schema = server_module._CONFIGURE_TOOL.inputSchema

    assert {"project_id", "root_path"} <= set(schema["properties"])
    assert schema["required"] == ["profile"]


@pytest.mark.anyio
async def test_configure_project_creates_missing_files(monkeypatch):
    root = Path(tempfile.mkdtemp())
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))
    _stub_profile_catalog(monkeypatch, {})

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("higpertext-configure-project", {"profile": "dev"})

    assert result.isError is False
    assert json.loads((root / ".higpertext/config/environment.json").read_text()) == {
        "active_profile": "dev"
    }
    assert json.loads((root / ".higpertext/config/mcp_external.json").read_text()) == {"servers": []}
    generated_mcp = json.loads((root / ".mcp.json").read_text())
    assert generated_mcp["mcpServers"]["higpertext"] == {
        "type": "http", "url": "http://127.0.0.1:8790/mcp/"
    }


def test_adapter_renderer_matches_migrated_layout_without_subagents(tmp_path):
    """La migración conserva playbooks y archivos nativos, no agentes delegados.

    Esta prueba es deliberadamente de estructura: impide que futuras ediciones
    vuelvan a crear los directorios ``agents``/``subagents`` de la CLI.
    """
    result = adapter_renderer.render(
        tmp_path,
        ["codex", "claude", "gemini", "copilot", "antigravity", "opencode"],
        "dev",
        [_GREP_SEARCH],
        [],
    )

    # SKILL.md ya no sale de adapter_renderer.render() — lo materializa
    # skill_renderer.render() por separado (ver test_skill_renderer_writes_
    # scoped_skills_across_assistants), igual que hook_renderer con los hooks.
    expected = {
        "AGENTS.md", "CLAUDE.md", ".clauderules", "GEMINI.md", "opencode.json",
        ".codex/rules/higpertext_rules.md", ".claude/rules/dev.md",
        ".gemini/workflows/plan.md",
        ".github/copilot-instructions.md", ".agents/mcp_config.json",
        ".agents/settings.json", ".agents/workflows/spec.md",
        ".opencode/rules/dev.md",
    }
    assert expected <= set(result["files"])
    assert "common.graph-query" in (tmp_path / ".agents/workflows/plan.md").read_text()
    assert "Active subagents" not in (tmp_path / ".agents/workflows/plan.md").read_text()
    assert not (tmp_path / ".agents/agents").exists()
    assert not (tmp_path / ".agents/subagents").exists()
    assert not (tmp_path / ".gemini/subagents").exists()
    assert not (tmp_path / ".github/agents").exists()
    assert not (tmp_path / ".opencode/agents").exists()


def test_adapter_renderer_adds_shared_mcp_for_any_adapter_and_preserves_servers(tmp_path):
    existing = {"mcpServers": {"other": {"command": "other-mcp"}}}
    (tmp_path / ".mcp.json").write_text(json.dumps(existing), encoding="utf-8")

    adapter_renderer.render(tmp_path, ["claude"], "dev", [], [])

    generated = json.loads((tmp_path / ".mcp.json").read_text())
    assert generated["mcpServers"]["other"] == {"command": "other-mcp"}
    assert generated["mcpServers"]["higpertext"] == {
        "type": "http",
        "url": "http://127.0.0.1:8790/mcp/",
    }


def test_adapter_renderer_does_not_rewrite_existing_higpertext_server(tmp_path):
    existing = {
        "mcpServers": {
            "higpertext": {"command": "custom-higpertext", "args": ["serve"]},
        },
    }
    path = tmp_path / ".mcp.json"
    path.write_text(json.dumps(existing), encoding="utf-8")

    result = adapter_renderer.render(tmp_path, ["gemini"], "dev", [], [])

    assert json.loads(path.read_text()) == existing
    assert ".mcp.json" not in result["files"]


def test_adapter_rules_use_profile_identity_and_mcp_discovery(tmp_path):
    profile = profile_pb2.Profile(
        name="secure-dev",
        description="Entrega cambios seguros y verificables.",
        system_prompt="Prioriza evidencia antes de editar.",
        rules=["No revelar secretos."],
    )
    adapter_renderer.render(tmp_path, ["codex"], profile, [_GREP_SEARCH], [])
    content = (tmp_path / "AGENTS.md").read_text()
    assert "Entrega cambios seguros y verificables." in content
    assert "Prioriza evidencia antes de editar." in content
    assert "No revelar secretos." in content
    assert "common.grep-search" not in content
    assert "consulta las tools MCP disponibles" in content


@pytest.mark.anyio
async def test_hook_renderer_writes_claude_effective_hooks(monkeypatch, tmp_path):
    hook = profile_pb2.HookDefinition(
        id="guard", event="PreToolUse", matcher="Bash", script="hooks/guard.py", timeout=5
    )

    async def fake_list_hooks(profile, assistant):
        assert (profile, assistant) == ("dev", "claude")
        return [hook]

    monkeypatch.setattr(hook_renderer.profile_client, "list_hooks", fake_list_hooks)
    output = await hook_renderer.render(tmp_path, "dev", ["claude"])
    settings = json.loads((tmp_path / ".claude/settings.json").read_text())
    assert "PreToolUse" in settings["hooks"]
    command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert command == "higpertext-hook guard --assistant claude --event PreToolUse"
    assert ".claude/settings.json" in output["claude"]


@pytest.mark.anyio
async def test_skill_renderer_scopes_by_project_and_profile_and_prunes_stale(monkeypatch, tmp_path):
    """SKILL.md sale del catálogo de SkillService, no de un diccionario
    hardcodeado (ver adapter_renderer.WORKFLOWS, que ya no las escribe).

    Cubre las tres reglas de scope acordadas: global (sin profiles ni
    project_id) siempre visible, project_id exacto visible solo para ese
    proyecto, profile visible solo si está en `profiles`; y que una skill
    materializada en una corrida previa que ya no aplica se borra (prune).
    """
    skills = [
        {"id": "common.build", "content": "common.build content", "profiles": [], "project_id": ""},
        {"id": "docs-api-style", "content": "docs-api-style content", "profiles": [], "project_id": "proj-123"},
        {"id": "other-project-skill", "content": "irrelevant", "profiles": [], "project_id": "proj-999"},
        {"id": "profile-scoped", "content": "profile-scoped content", "profiles": ["dev"], "project_id": ""},
        {"id": "other-profile-scoped", "content": "irrelevant", "profiles": ["other"], "project_id": ""},
    ]

    async def fake_list_skills(*, enabled_only=False):
        return skills

    async def fake_resolve_project(root_path):
        assert root_path == str(tmp_path)
        return {"id": "proj-123", "root_path": root_path, "root_path_hash": "x", "name": "dev"}

    monkeypatch.setattr(skill_renderer.profile_client, "list_skills", fake_list_skills)
    monkeypatch.setattr(skill_renderer.profile_client, "resolve_project", fake_resolve_project)

    # Simula una skill materializada en una corrida previa que ya no está en
    # el catálogo visible — debe ser podada.
    stale_dir = tmp_path / ".claude" / "skills" / "stale-skill"
    stale_dir.mkdir(parents=True)
    (stale_dir / "SKILL.md").write_text("old", encoding="utf-8")

    output = await skill_renderer.render(tmp_path, "dev", ["claude"])

    claude_dir = tmp_path / ".claude" / "skills"
    materialized = {p.name for p in claude_dir.iterdir()}
    assert materialized == {"common.build", "docs-api-style", "profile-scoped"}
    assert not stale_dir.exists()
    assert (claude_dir / "common.build" / "SKILL.md").read_text() == "common.build content"
    assert output[".claude/skills"]["pruned"] == ["stale-skill"]


@pytest.mark.anyio
async def test_call_unknown_tool_returns_is_error(monkeypatch):
    root = _make_project("dev")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))
    _stub_profile_catalog(monkeypatch, {"dev": [_GREP_SEARCH]})

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("common-no-existe", {})
        assert result.isError is True
        assert result.structuredContent["ok"] is False


@pytest.mark.anyio
async def test_call_tool_returns_structured_content(monkeypatch):
    root = _make_project("dev")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))
    _stub_profile_catalog(monkeypatch, {"dev": [_GREP_SEARCH]})

    async def fake_call_capability(*_args):
        return dispatch.CapabilityResult(
            ok=True,
            summary="One match found.",
            data={"matches": ["src/example.py:1"]},
            artifacts=[],
            warnings=[],
        )

    monkeypatch.setattr(dispatch, "call_capability", fake_call_capability)

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("common-grep-search", {"pattern": "example"})
        assert result.isError is False
        assert result.content[0].text == "One match found."
        assert result.structuredContent["data"]["matches"] == ["src/example.py:1"]


@pytest.mark.anyio
async def test_list_resources_exposes_usage_and_memory(monkeypatch):
    root = _make_project("dev")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))
    _stub_profile_catalog(monkeypatch, {"dev": []})

    async def fake_list_memory(_root):
        return []

    monkeypatch.setattr("higpertext_mcp.resources.memory.list_memory", fake_list_memory)

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.list_resources()
        uris = {str(r.uri) for r in result.resources}
        assert "higpertext://session/usage" in uris
        assert "higpertext://session/memory" in uris

        read = await client.read_resource("higpertext://session/usage")
        payload = json.loads(read.contents[0].text)
        assert payload == {"total_tokens": 0, "total_cost_usd": 0.0, "calls": 0, "by_tool": {}}

        read = await client.read_resource("higpertext://session/memory")
        payload = json.loads(read.contents[0].text)
        assert payload == {"entries": []}
