import json
import tempfile
from pathlib import Path

import mcp.types as types
import pytest

from higpertext_mcp import external


def _make_config_dir(root: Path, servers: list[dict] | dict) -> None:
    config_dir = root / ".higpertext" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = servers if isinstance(servers, dict) else {"servers": servers}
    (config_dir / "mcp_external.json").write_text(json.dumps(payload), encoding="utf-8")


class TestLoadExternalServers:
    def test_missing_file_returns_empty(self):
        root = Path(tempfile.mkdtemp())
        assert external.load_external_servers(root) == []

    def test_corrupt_json_returns_empty(self):
        root = Path(tempfile.mkdtemp())
        config_dir = root / ".higpertext" / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "mcp_external.json").write_text("{not json", encoding="utf-8")
        assert external.load_external_servers(root) == []

    def test_reads_valid_server_entry(self):
        root = Path(tempfile.mkdtemp())
        _make_config_dir(
            root, [{"name": "github", "command": "npx", "args": ["-y", "server-github"]}]
        )
        configs = external.load_external_servers(root)
        assert len(configs) == 1
        assert configs[0].name == "github"
        assert configs[0].command == "npx"
        assert configs[0].args == ["-y", "server-github"]

    def test_skips_entry_without_name(self):
        root = Path(tempfile.mkdtemp())
        _make_config_dir(root, [{"command": "npx"}])
        assert external.load_external_servers(root) == []

    def test_skips_entry_without_command(self):
        root = Path(tempfile.mkdtemp())
        _make_config_dir(root, [{"name": "github"}])
        assert external.load_external_servers(root) == []

    def test_skips_non_dict_entry_but_keeps_valid_ones(self):
        root = Path(tempfile.mkdtemp())
        _make_config_dir(root, ["not-a-dict", {"name": "ok", "command": "cmd"}])
        configs = external.load_external_servers(root)
        assert len(configs) == 1
        assert configs[0].name == "ok"

    def test_servers_not_a_list_returns_empty(self):
        root = Path(tempfile.mkdtemp())
        _make_config_dir(root, {"servers": "not-a-list"})
        assert external.load_external_servers(root) == []


class _FakeSession:
    """Sesión MCP falsa para testear ExternalServerPool sin subprocess real."""

    def __init__(self, tools: list[types.Tool], call_result: types.CallToolResult | None = None,
                 fail_list: bool = False, fail_call: bool = False) -> None:
        self._tools = tools
        self._call_result = call_result
        self._fail_list = fail_list
        self._fail_call = fail_call
        self.called_with: tuple[str, dict] | None = None

    async def list_tools(self) -> types.ListToolsResult:
        if self._fail_list:
            raise RuntimeError("boom: list_tools failed")
        return types.ListToolsResult(tools=self._tools)

    async def call_tool(self, name: str, arguments: dict) -> types.CallToolResult:
        if self._fail_call:
            raise RuntimeError("boom: call_tool failed")
        self.called_with = (name, arguments)
        return self._call_result or types.CallToolResult(
            content=[types.TextContent(type="text", text="ok")], isError=False
        )


def _tool(name: str, description: str = "desc") -> types.Tool:
    return types.Tool(name=name, description=description, inputSchema={"type": "object"})


class TestExternalServerPoolMerging:
    @pytest.mark.anyio
    async def test_merges_and_prefixes_tool_names(self):
        session = _FakeSession([_tool("search")])
        pool = external.ExternalServerPool.from_sessions({"github": session})
        merged = await pool.list_tools_merged()
        assert [t.name for t in merged] == ["external.github.search"]
        assert merged[0].description.startswith("[external:github]")

    @pytest.mark.anyio
    async def test_merges_tools_from_multiple_servers(self):
        pool = external.ExternalServerPool.from_sessions(
            {
                "github": _FakeSession([_tool("search")]),
                "slack": _FakeSession([_tool("post")]),
            }
        )
        merged = await pool.list_tools_merged()
        names = {t.name for t in merged}
        assert names == {"external.github.search", "external.slack.post"}

    @pytest.mark.anyio
    async def test_dead_session_drops_silently_without_raising(self):
        pool = external.ExternalServerPool.from_sessions(
            {
                "broken": _FakeSession([], fail_list=True),
                "alive": _FakeSession([_tool("ok")]),
            }
        )
        merged = await pool.list_tools_merged()
        assert [t.name for t in merged] == ["external.alive.ok"]


class TestExternalServerPoolCallTool:
    @pytest.mark.anyio
    async def test_forwards_to_correct_session(self):
        session = _FakeSession([_tool("search")])
        pool = external.ExternalServerPool.from_sessions({"github": session})
        await pool.list_tools_merged()
        result = await pool.call_tool("external.github.search", {"q": "x"})
        assert result.isError is False
        assert session.called_with == ("search", {"q": "x"})

    @pytest.mark.anyio
    async def test_resolves_without_prior_list_tools_call(self):
        session = _FakeSession([_tool("search")])
        pool = external.ExternalServerPool.from_sessions({"github": session})
        result = await pool.call_tool("external.github.search", {})
        assert result.isError is False
        assert session.called_with == ("search", {})

    @pytest.mark.anyio
    async def test_forwards_even_tool_name_not_in_last_list(self):
        """No hay validación de existencia en la pool — se reenvía y el servidor externo decide."""
        session = _FakeSession([_tool("search")])
        pool = external.ExternalServerPool.from_sessions({"github": session})
        result = await pool.call_tool("external.github.does-not-exist", {})
        assert result.isError is False
        assert session.called_with == ("does-not-exist", {})

    @pytest.mark.anyio
    async def test_unknown_server_returns_error(self):
        pool = external.ExternalServerPool.from_sessions({"github": _FakeSession([_tool("search")])})
        result = await pool.call_tool("external.unknown-server.search", {})
        assert result.isError is True

    @pytest.mark.anyio
    async def test_exception_during_call_returns_error_result(self):
        session = _FakeSession([_tool("search")], fail_call=True)
        pool = external.ExternalServerPool.from_sessions({"github": session})
        result = await pool.call_tool("external.github.search", {})
        assert result.isError is True

    @pytest.mark.anyio
    async def test_non_external_name_returns_error(self):
        pool = external.ExternalServerPool.from_sessions({"github": _FakeSession([_tool("search")])})
        result = await pool.call_tool("common.grep-search", {})
        assert result.isError is True


class TestExternalServerPoolNoop:
    @pytest.mark.anyio
    async def test_empty_pool_list_tools_is_empty(self):
        pool = external.ExternalServerPool()
        assert await pool.list_tools_merged() == []

    @pytest.mark.anyio
    async def test_empty_pool_start_and_close_are_noop(self):
        pool = external.ExternalServerPool()
        await pool.start()
        await pool.aclose()

    @pytest.mark.anyio
    async def test_empty_pool_has_tool_false(self):
        pool = external.ExternalServerPool()
        assert pool.has_tool("external.github.search") is False


class TestExternalServerPoolStart:
    @pytest.mark.anyio
    async def test_start_skips_server_that_fails_without_crashing_others(self, monkeypatch):
        good_session = _FakeSession([_tool("ok")])

        class _FailingStdioClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                raise RuntimeError("cannot spawn")

            async def __aexit__(self, *exc):
                return False

        call_count = {"n": 0}

        def fake_stdio_client(params):
            call_count["n"] += 1
            if params.command == "broken-cmd":
                return _FailingStdioClient()
            raise AssertionError("only 'broken-cmd' expected to reach stdio_client in this test")

        monkeypatch.setattr(external, "stdio_client", fake_stdio_client)

        configs = [
            external.ExternalServerConfig(name="broken", command="broken-cmd"),
        ]
        pool = external.ExternalServerPool(configs)
        await pool.start()  # no debe lanzar
        assert await pool.list_tools_merged() == []
        await pool.aclose()


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
