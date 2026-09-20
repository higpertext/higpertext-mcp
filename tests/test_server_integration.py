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

from higpertext_mcp import adapter_renderer, agent_renderer, discovery, dispatch, hook_renderer, skill_renderer, server as server_module
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
        assert names == {"higpertext-configure-project", "higpertext-render-adapters", "higpertext-governance-rule", "higpertext-governance-exception", "higpertext-profile", "higpertext-capability", "higpertext-hook-admin", "higpertext-skill", "higpertext-agent", "common-grep-search", "git-diff"}
        grep_tool = next(t for t in result.tools if t.name == "common-grep-search")
        assert grep_tool.annotations.readOnlyHint is True
        assert "pattern" in grep_tool.inputSchema["properties"]


def test_render_adapters_requires_project_selector_but_accepts_either_form():
    schema = server_module._RENDER_ADAPTERS_TOOL.inputSchema

    assert schema["oneOf"] == [{"required": ["project_id"]}, {"required": ["root_path"]}]
    assert "required" not in schema
    assert "project_id" in schema["properties"]
    assert "root_path" in schema["properties"]
    assert "assistants" in schema["properties"]
    assert "exactamente uno" in server_module._RENDER_ADAPTERS_TOOL.description


def test_dynamic_capability_schema_is_strict_and_uses_declared_type():
    capability = profile_pb2.Capability(
        id="custom.tool",
        description="tool",
        parameters=[
            profile_pb2.Parameter(name="enabled", type="bool", required=True),
            profile_pb2.Parameter(name="count", type="int", default="2"),
        ],
    )
    tool = server_module._to_mcp_tool(
        capability.id, server_module.schema.tool_spec_from_capability(capability)
    )
    assert tool.inputSchema["additionalProperties"] is False
    assert tool.inputSchema["properties"]["enabled"]["type"] == "boolean"
    assert tool.inputSchema["properties"]["count"]["type"] == "integer"
    assert tool.inputSchema["properties"]["count"]["default"] == 2


def test_admin_schemas_expose_dispatch_parameters():
    hook_schema = server_module._HOOK_TOOL.inputSchema
    assert "script" in hook_schema["properties"]

    capability_item = server_module._CAPABILITY_TOOL.inputSchema["properties"]["parameters"]["items"]
    assert capability_item["additionalProperties"] is False

    skill_schema = server_module._SKILL_TOOL.inputSchema
    # These selectors are accepted by SkillService.ListSkills and must remain
    # visible to the MCP client instead of being hidden by an old schema.
    assert "profile" in skill_schema["properties"]
    assert "project_id" in skill_schema["properties"]


def test_configure_project_accepts_project_selector():
    schema = server_module._CONFIGURE_TOOL.inputSchema

    assert {"project_id", "root_path"} <= set(schema["properties"])
    assert schema["required"] == ["profile"]


@pytest.mark.anyio
async def test_invalid_tool_arguments_return_actionable_result(monkeypatch):
    root = _make_project("dev")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))
    _stub_profile_catalog(monkeypatch, {})

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(
            "higpertext-render-adapters", {"assistants": ["codex"]}
        )

    assert result.isError is True
    assert "project_id" in result.content[0].text
    assert "root_path" in result.content[0].text
    assert "not valid under any" not in result.content[0].text
    assert result.structuredContent["error"]["code"] == "invalid_arguments"


@pytest.mark.anyio
async def test_missing_configure_profile_returns_common_argument_error(monkeypatch):
    root = _make_project("dev")
    monkeypatch.setenv("HIGPERTEXT_PROJECT_ROOT", str(root))
    _stub_profile_catalog(monkeypatch, {})

    server = server_module.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("higpertext-configure-project", {})

    assert result.isError is True
    assert result.content[0].text.endswith("'profile' es obligatorio.")
    assert result.structuredContent["error"]["code"] == "invalid_arguments"


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


def test_agent_render_md_omits_unset_optional_fields():
    agent = {
        "id": "mcp-test-runner", "name": "mcp-test-runner", "description": "runs tests",
        "tools": ["Read", "Grep", "Glob", "Bash"], "model": "sonnet", "prompt": "You run tests.",
        "permission_mode": "", "skills": [], "memory": "", "background": None, "color": "", "effort": "",
    }
    rendered = agent_renderer._render_claude(agent)
    assert rendered.startswith(
        "---\nname: mcp-test-runner\ndescription: runs tests\ntools: Read, Grep, Glob, Bash\nmodel: sonnet\n---\n\n"
    )
    assert "permissionMode" not in rendered
    assert "background" not in rendered
    assert agent_renderer._MARKER_TEXT in rendered


def test_agent_render_codex_toml_omits_fields_without_codex_equivalent():
    agent = {
        "id": "mcp-test-runner", "name": "mcp-test-runner", "description": "runs tests",
        "tools": ["Read", "Grep", "Glob", "Bash"], "model": "gpt-5-codex", "prompt": "You run tests.",
        "permission_mode": "acceptEdits", "skills": ["common.build"], "memory": "notes", "color": "blue",
        "effort": "high",
    }
    rendered = agent_renderer._render_codex(agent)
    assert rendered.startswith(
        'name = "mcp-test-runner"\ndescription = "runs tests"\n'
        'developer_instructions = """\nYou run tests.\n"""\n'
        'model = "gpt-5-codex"\nmodel_reasoning_effort = "high"\n'
    )
    # Sin equivalente en el schema de Codex: se omiten a propósito, no se
    # fuerza un mapeo aproximado (tools/permission_mode/skills/memory/color).
    for absent in ("tools", "sandbox_mode", "skills", "memory", "color", "acceptEdits", "blue"):
        assert absent not in rendered
    assert agent_renderer._MARKER_TEXT in rendered


@pytest.mark.anyio
async def test_agent_renderer_scopes_and_prunes_stale_and_respects_unmanaged_files(monkeypatch, tmp_path):
    """Calco de test_skill_renderer_scopes_by_project_and_profile_and_prunes_stale,
    adaptado a archivos planos + contenido sintetizado, más el mecanismo de
    ownership propio de agent_renderer: un .md preexistente sin la marca
    `managed_by` nunca se sobreescribe ni se poda."""
    agents = [
        {"id": "global-agent", "name": "global-agent", "description": "d", "tools": [], "model": "sonnet",
         "prompt": "global prompt", "profiles": [], "project_id": ""},
        {"id": "project-agent", "name": "project-agent", "description": "d", "tools": [], "model": "sonnet",
         "prompt": "project prompt", "profiles": [], "project_id": "proj-123"},
        {"id": "other-project-agent", "name": "other-project-agent", "description": "d", "tools": [], "model": "sonnet",
         "prompt": "irrelevant", "profiles": [], "project_id": "proj-999"},
        {"id": "profile-agent", "name": "profile-agent", "description": "d", "tools": [], "model": "sonnet",
         "prompt": "profile prompt", "profiles": ["dev"], "project_id": ""},
        {"id": "other-profile-agent", "name": "other-profile-agent", "description": "d", "tools": [], "model": "sonnet",
         "prompt": "irrelevant", "profiles": ["other"], "project_id": ""},
    ]

    async def fake_list_agents(*, profile="", project_id=""):
        return agents

    async def fake_resolve_project(root_path):
        assert root_path == str(tmp_path)
        return {"id": "proj-123", "root_path": root_path, "root_path_hash": "x", "name": "dev"}

    monkeypatch.setattr(agent_renderer.profile_client, "list_agents", fake_list_agents)
    monkeypatch.setattr(agent_renderer.profile_client, "resolve_project", fake_resolve_project)

    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    # Managed, stale (ya no está en el catálogo visible) — debe podarse.
    stale = agents_dir / "stale-agent.md"
    stale.write_text(f"stale content\n\n<!-- {agent_renderer._MARKER_TEXT} -->\n", encoding="utf-8")

    # Sin marca de ownership y con id colisionando con un agent visible del
    # catálogo — editado a mano, nunca se sobreescribe.
    unmanaged = agents_dir / "profile-agent.md"
    unmanaged.write_text("# hand made, no marker here\n", encoding="utf-8")

    output = await agent_renderer.render(tmp_path, "dev", ["claude"])

    materialized = {p.name for p in agents_dir.iterdir()}
    assert materialized == {
        "global-agent.md", "project-agent.md", "profile-agent.md",
    }
    assert not stale.exists()
    assert unmanaged.read_text(encoding="utf-8") == "# hand made, no marker here\n"
    assert (agents_dir / "global-agent.md").read_text(encoding="utf-8") == agent_renderer._render_claude(agents[0])

    result = output[".claude/agents"]
    assert set(result["written"]) == {
        ".claude/agents/global-agent.md", ".claude/agents/project-agent.md",
    }
    assert result["pruned"] == ["stale-agent"]
    assert result["skipped_unmanaged"] == [".claude/agents/profile-agent.md"]


@pytest.mark.anyio
async def test_agent_renderer_filters_by_assistant(monkeypatch, tmp_path):
    agents = [
        {"id": "claude-only", "name": "claude-only", "description": "d", "tools": [], "model": "sonnet", "prompt": "p", "assistants": ["claude"]},
        {"id": "codex-only", "name": "codex-only", "description": "d", "tools": [], "model": "gpt-5", "prompt": "p", "assistants": ["codex"]},
        {"id": "all", "name": "all", "description": "d", "tools": [], "model": "sonnet", "prompt": "p", "assistants": []},
    ]

    async def fake_list_agents(*, profile="", project_id=""):
        return agents

    async def fake_resolve_project(root_path):
        return {"id": "proj-123", "root_path": root_path}

    monkeypatch.setattr(agent_renderer.profile_client, "list_agents", fake_list_agents)
    monkeypatch.setattr(agent_renderer.profile_client, "resolve_project", fake_resolve_project)

    await agent_renderer.render(tmp_path, "dev", ["claude", "codex"])
    assert {p.stem for p in (tmp_path / ".claude/agents").iterdir()} == {"claude-only", "all"}
    assert {p.stem for p in (tmp_path / ".codex/agents").iterdir()} == {"codex-only", "all"}


@pytest.mark.anyio
async def test_agent_renderer_targets_codex_toml_alongside_claude(monkeypatch, tmp_path):
    """Un mismo catálogo se materializa en formatos distintos por asistente,
    igual que hook_renderer con los 6 asistentes de hooks — acá con dos
    destinos de extensión y contenido totalmente distintos (.md YAML+MD vs
    .toml)."""
    agents = [
        {"id": "global-agent", "name": "global-agent", "description": "d", "tools": [], "model": "sonnet",
         "prompt": "global prompt", "profiles": [], "project_id": ""},
    ]

    async def fake_list_agents(*, profile="", project_id=""):
        return agents

    async def fake_resolve_project(root_path):
        return {"id": "proj-123", "root_path": root_path, "root_path_hash": "x", "name": "dev"}

    monkeypatch.setattr(agent_renderer.profile_client, "list_agents", fake_list_agents)
    monkeypatch.setattr(agent_renderer.profile_client, "resolve_project", fake_resolve_project)

    output = await agent_renderer.render(tmp_path, "dev", ["claude", "codex"])

    assert (tmp_path / ".claude/agents/global-agent.md").exists()
    codex_path = tmp_path / ".codex/agents/global-agent.toml"
    assert codex_path.exists()
    assert codex_path.read_text(encoding="utf-8") == agent_renderer._render_codex(agents[0])
    assert output[".claude/agents"]["written"] == [".claude/agents/global-agent.md"]
    assert output[".codex/agents"]["written"] == [".codex/agents/global-agent.toml"]

    # Pedir solo "claude" no debe tocar el destino de codex.
    output_claude_only = await agent_renderer.render(tmp_path, "dev", ["claude"])
    assert list(output_claude_only.keys()) == [".claude/agents"]
    assert codex_path.exists()


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
