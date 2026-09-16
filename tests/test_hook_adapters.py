import asyncio
import json
from types import SimpleNamespace

import pytest

from higpertext_mcp import events, hook_invoker, hook_protocol, hook_renderer


def hook(id="hook_bash_guard", event="PreToolUse", matcher="Bash", timeout=10):
    return SimpleNamespace(id=id, event=event, matcher=matcher, timeout=timeout)


@pytest.mark.parametrize("assistant", [a for a in hook_protocol.EVENTS if a != "opencode"])
def test_render_preserves_external_and_is_idempotent(tmp_path, monkeypatch, assistant):
    async def listing(*args):
        return [hook(), hook("hook_read_guard", matcher="Read")]
    monkeypatch.setattr(hook_renderer.profile_client, "list_hooks", listing)
    path = tmp_path / hook_renderer._SETTINGS_PATH[assistant]
    path.parent.mkdir(parents=True)
    foreign = {"type": "command", "command": "external-check"}
    if assistant == "antigravity":
        initial = {"external": {"PreToolUse": [{"hooks": [foreign]}]}}
    else:
        initial = {"otherSetting": True, "hooks": {"PreToolUse": [{"matcher": ".*", "hooks": [foreign, {"command": "higpertext-hook old"}]}]}}
    path.write_text(json.dumps(initial))
    asyncio.run(hook_renderer.render(tmp_path, "test", [assistant]))
    first = path.read_text()
    asyncio.run(hook_renderer.render(tmp_path, "test", [assistant]))
    assert path.read_text() == first
    assert "external-check" in first
    assert "higpertext-hook old" not in first
    assert first.count("higpertext-hook hook_") == 2
    result = json.loads(first)
    if assistant == "gemini":
        assert len(result["hooks"]["BeforeTool"]) == 2
        assert result["hooks"]["BeforeTool"][0]["hooks"][0]["timeout"] == 10000
        assert result["hooks"]["BeforeTool"][0]["matcher"] == "run_shell_command"


def test_invalid_destination_does_not_partially_write(tmp_path, monkeypatch):
    async def listing(*args):
        return [hook()]
    monkeypatch.setattr(hook_renderer.profile_client, "list_hooks", listing)
    path = tmp_path / ".gemini/settings.json"
    path.parent.mkdir()
    path.write_text("[]")
    with pytest.raises(ValueError):
        asyncio.run(hook_renderer.render(tmp_path, "test", ["claude", "gemini"]))
    assert not (tmp_path / ".claude").exists()


@pytest.mark.parametrize("assistant", ["unknown"])
def test_unsupported_is_explicit(tmp_path, assistant):
    with pytest.raises(ValueError, match="not supported"):
        asyncio.run(hook_renderer.render(tmp_path, "test", [assistant]))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("assistant,payload", [
    ("claude", {"tool_name": "Bash", "tool_input": {"command": "echo harmless"}}),
    ("codex", {"tool_name": "Bash", "tool_input": {"command": "echo harmless"}}),
    ("gemini", {"tool_name": "run_shell_command", "tool_input": {"command": "echo harmless"}}),
    ("copilot", {"toolName": "bash", "toolArgs": '{"command":"echo harmless"}'}),
    ("antigravity", {"toolCall": {"name": "run_command", "args": {"CommandLine": "echo harmless"}}}),
])
def test_native_shell_payload_is_canonical(assistant, payload):
    result = hook_protocol.normalize(assistant, "PreToolUse", payload)
    assert result["tool_name"] == "Bash"
    assert result["tool_input"]["command"] == "echo harmless"
    assert result["hook_event_name"] == "PreToolUse"
    assert result["canonical_event"] == events.EventType.ACTION_REQUESTED.value
    assert result["event_observation"] == "observed"


@pytest.mark.parametrize("assistant,native,canonical", [
    ("claude", "PreToolUse", events.EventType.ACTION_REQUESTED),
    ("claude", "PostToolUse", events.EventType.ACTION_COMPLETED),
    ("claude", "UserPromptSubmit", events.EventType.PROMPT_RECEIVED),
    ("claude", "PreCompact", events.EventType.CONTEXT_COMPACTING),
    ("claude", "Stop", events.EventType.SESSION_FINISHED),
])
def test_native_events_translate_to_canonical_events(assistant, native, canonical):
    assert events.canonical_type(assistant, native) is canonical


def test_authorization_is_never_claimed_by_an_adapter():
    for capabilities in events.ADAPTERS.values():
        assert events.EventType.ACTION_AUTHORIZED in capabilities.unsupported
        assert any("gateway/controller" in limitation for limitation in capabilities.limitations)


def test_unsupported_native_event_is_explicit():
    with pytest.raises(ValueError, match="not supported"):
        events.canonical_type("opencode", "UserPromptSubmit")


@pytest.mark.parametrize("assistant", hook_protocol.EVENTS)
def test_deny_and_abstain_do_not_grant_permissions(assistant):
    result = hook_protocol.encode(assistant, "PreToolUse", {"continue": False})
    if assistant in {"claude", "codex", "opencode"}:
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    elif assistant == "copilot":
        assert result["permissionDecision"] == "deny"
    else:
        assert result["decision"] == "deny"
    permitted = hook_protocol.encode(assistant, "PreToolUse", {"continue": True})
    assert "allow" not in json.dumps(permitted)


@pytest.mark.parametrize("assistant", hook_protocol.EVENTS)
def test_invoker_failure_denies_in_native_protocol(monkeypatch, capsys, assistant):
    import io
    async def fail(*args):
        raise RuntimeError("sensitive backend detail")
    monkeypatch.setattr(hook_invoker.hook_runner, "resolve_hook_script", fail)
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    monkeypatch.setattr("sys.argv", ["higpertext-hook", "guard", "--assistant", assistant, "--event", "PreToolUse"])
    hook_invoker.main()
    captured = capsys.readouterr()
    assert "sensitive backend detail" not in captured.out + captured.err
    assert "deny" in json.dumps(json.loads(captured.out))


@pytest.mark.parametrize("assistant", hook_protocol.EVENTS)
def test_invoker_delivers_normalized_input_and_translates_hook_output(monkeypatch, capsys, assistant):
    import io
    async def resolve(*args):
        return "unused"
    def run(*args):
        payload = json.load(__import__("sys").stdin)
        assert payload["hook_event_name"] == "PreToolUse"
        print(json.dumps({"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": "fixture denial"}}))
        return 0
    monkeypatch.setattr(hook_invoker.hook_runner, "resolve_hook_script", resolve)
    monkeypatch.setattr(hook_invoker.hook_runner, "run_hook", run)
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    monkeypatch.setattr("sys.argv", ["higpertext-hook", "guard", "--assistant", assistant, "--event", "PreToolUse"])
    hook_invoker.main()
    result = json.loads(capsys.readouterr().out)
    assert "fixture denial" in json.dumps(result)


def test_injection_and_foreign_pipeline():
    with pytest.raises(ValueError):
        hook_renderer._plan({}, "claude", [hook("guard;touch /tmp/bad")])
    assert not hook_renderer._managed({"command": "higpertext-hook guard && external"})


def test_multi_path_patch_is_preserved():
    patch = "*** Begin Patch\n*** Update File: a.py\n*** Update File: b.py\n*** End Patch"
    result = hook_protocol.normalize("codex", "PreToolUse", {"tool_name": "apply_patch", "tool_input": {"command": patch}})
    assert result["tool_name"] == "apply_patch"
    assert result["tool_input"]["command"] == patch


def test_opencode_bridge_blocks_and_preserves_unmanaged_plugin(tmp_path):
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("node not installed")
    plugin = tmp_path / "plugin.mjs"
    plugin.write_text(hook_renderer._opencode_plan(plugin, [hook()]))
    # Exercise the JS callback with a fake transport, not a live DB hook.
    source = plugin.read_text().replace("import { spawnSync } from 'node:child_process';", "const spawnSync = () => ({status: 0, stdout: JSON.stringify({hookSpecificOutput: {permissionDecision: 'deny', permissionDecisionReason: 'fixture denial'}})});")
    plugin.write_text(source)
    harness = tmp_path / "check.mjs"
    harness.write_text("""
import { HigpertextHooks } from './plugin.mjs';
const plugin = await HigpertextHooks({ directory: process.cwd() });
let blocked = false;
try { await plugin['tool.execute.before']({tool: 'bash'}, {args: {command: 'echo harmless'}}); }
catch (error) { blocked = error.message === 'fixture denial'; }
if (!blocked) process.exit(1);
await plugin['tool.execute.before']({tool: 'read'}, {args: {filePath: 'safe.txt'}});
""")
    subprocess.run(["node", str(harness)], check=True, capture_output=True)
    plugin.write_text("// user plugin\n")
    with pytest.raises(ValueError, match="unmanaged"):
        hook_renderer._opencode_plan(plugin, [hook()])


def test_render_all_six(tmp_path, monkeypatch):
    async def listing(*args):
        return [hook()]
    monkeypatch.setattr(hook_renderer.profile_client, "list_hooks", listing)
    result = asyncio.run(hook_renderer.render(tmp_path, "test", []))
    assert set(result) == set(hook_protocol.EVENTS)
    assert all((tmp_path / files[0]).exists() for files in result.values())
