"""run_async debe conservar los contextvars (raíz del request) al delegar a un hilo."""
import asyncio
import contextvars

from higpertext_mcp import board_client

_var: contextvars.ContextVar[str] = contextvars.ContextVar("probe", default="proceso")


def test_run_async_preserves_contextvars_inside_running_loop():
    async def read() -> str:
        return _var.get()

    async def caller() -> str:
        _var.set("request")
        return board_client.run_async(read())

    assert asyncio.run(caller()) == "request"
