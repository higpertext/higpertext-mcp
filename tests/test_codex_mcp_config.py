"""El adapter de Codex declara la raíz del proyecto en `.codex/config.toml`."""
import tomllib

from higpertext_mcp import adapter_renderer, discovery


def _header(path):
    table = tomllib.loads(path.read_text(encoding="utf-8"))["mcp_servers"]["higpertext"]
    return table["http_headers"][discovery.PROJECT_ROOT_HEADER]


def test_creates_config_with_root_header(tmp_path):
    written: list[str] = []
    adapter_renderer._ensure_codex_mcp(tmp_path, written)
    assert _header(tmp_path / ".codex" / "config.toml") == str(tmp_path.resolve())


def test_preserves_other_tables_and_replaces_stale_one(tmp_path):
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir()
    cfg.write_text(
        '[mcp_servers.higpertext-mcp]\nurl = "http://x/"\n\n'
        '[mcp_servers.higpertext]\nurl = "http://old/"\nenabled = true\n\n'
        '[projects."/a"]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    adapter_renderer._ensure_codex_mcp(tmp_path, [])
    data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    assert data["mcp_servers"]["higpertext-mcp"]["url"] == "http://x/"
    assert data["projects"]["/a"]["trust_level"] == "trusted"
    assert _header(cfg) == str(tmp_path.resolve())


def test_idempotent(tmp_path):
    adapter_renderer._ensure_codex_mcp(tmp_path, [])
    written: list[str] = []
    adapter_renderer._ensure_codex_mcp(tmp_path, written)
    assert written == []
