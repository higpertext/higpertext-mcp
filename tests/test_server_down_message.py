import io
import json

import grpc
import pytest

from higpertext_mcp import hook_invoker, hook_protocol, profile_client


def _rpc_error(code: grpc.StatusCode) -> grpc.aio.AioRpcError:
    return grpc.aio.AioRpcError(
        code, grpc.aio.Metadata(), grpc.aio.Metadata(), details="raw grpc detail", debug_error_string="dbg",
    )


@pytest.mark.parametrize("code", [grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED])
def test_describe_error_explains_unreachable_server(code):
    text = profile_client.describe_error(_rpc_error(code))
    assert "profile server no responde" in text
    assert "docker start" in text
    assert "AioRpcError" not in text and "raw grpc detail" not in text


def test_describe_error_keeps_other_errors_untouched():
    assert profile_client.describe_error(_rpc_error(grpc.StatusCode.NOT_FOUND)) == str(_rpc_error(grpc.StatusCode.NOT_FOUND))
    assert profile_client.describe_error(ValueError("action inválida")) == "action inválida"


@pytest.mark.anyio
async def test_get_hook_script_raises_when_server_is_down(monkeypatch):
    class Stub:
        def __init__(self, channel):
            pass

        async def GetHookScript(self, req, timeout):
            raise _rpc_error(grpc.StatusCode.UNAVAILABLE)

    monkeypatch.setattr(profile_client.profile_pb2_grpc, "HookServiceStub", Stub)
    with pytest.raises(profile_client.ProfileServerUnavailable):
        await profile_client.get_hook_script("hook_bash_guard")


@pytest.mark.anyio
async def test_get_hook_script_returns_none_for_other_errors(monkeypatch):
    class Stub:
        def __init__(self, channel):
            pass

        async def GetHookScript(self, req, timeout):
            raise _rpc_error(grpc.StatusCode.NOT_FOUND)

    monkeypatch.setattr(profile_client.profile_pb2_grpc, "HookServiceStub", Stub)
    assert await profile_client.get_hook_script("hook_inexistente") is None


def _run_invoker(monkeypatch, capsys, argv):
    async def down(*args):
        raise profile_client.ProfileServerUnavailable(profile_client.server_down_message())

    monkeypatch.setattr(hook_invoker.hook_runner, "resolve_hook_script", down)
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    monkeypatch.setattr("sys.argv", argv)
    hook_invoker.main()
    return capsys.readouterr()


@pytest.mark.parametrize("assistant", hook_protocol.EVENTS)
def test_invoker_denial_names_the_server_when_it_is_down(monkeypatch, capsys, assistant):
    captured = _run_invoker(
        monkeypatch, capsys, ["higpertext-hook", "guard", "--assistant", assistant, "--event", "PreToolUse"],
    )
    out = json.dumps(json.loads(captured.out))
    assert "deny" in out
    assert "profile server no responde" in out
    assert "profile server no responde" in captured.err


def test_invoker_legacy_wiring_reports_server_down(monkeypatch, capsys):
    captured = _run_invoker(monkeypatch, capsys, ["higpertext-hook", "guard"])
    result = json.loads(captured.out)
    assert result["continue"] is True
    assert "profile server no responde" in result["error"]
