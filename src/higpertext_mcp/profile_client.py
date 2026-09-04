"""Cliente gRPC hacia higpertext-server-profile: catálogo dinámico de capabilities
(reemplaza la resolución estática de `discovery.py`) y registro de actividad
(reemplaza el rol de `save_memory()` del lado "registro central", complementario
a `memory.py` que cubre el lado Redis).

Fail-closed en discovery (mismo criterio que `discovery.allowed_capabilities()`
tenía sin perfil legible: si el server no responde, no se expone nada en vez de
exponer un catálogo potencialmente desactualizado). Fail-open/silencioso en el
registro de actividad: un profile server caído nunca debe tumbar una respuesta MCP.
"""

from __future__ import annotations

import sys
from pathlib import Path

import grpc

sys.path.insert(0, str(Path(__file__).parent / "gen"))

from higpertext_mcp import config
from higpertext_mcp.gen.profile.v1 import profile_pb2, profile_pb2_grpc

_CALL_TIMEOUT_S = 2.0


def _warn(message: str) -> None:
    print(f"[higpertext-mcp/profile_client] {message}", file=sys.stderr)


async def list_allowed_capabilities(profile: str | None) -> list[profile_pb2.Capability]:
    """Intersección entre el perfil activo (ProfileService) y el catálogo
    (CapabilityService) del profile server, devolviendo los `Capability`
    completos (metadata: descripción, parámetros, contrato) — no solo ids.
    [] si no hay perfil, o si el server no responde — mismo fail-closed que
    la resolución estática que reemplaza.
    """
    if not profile:
        return []
    try:
        async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
            profile_stub = profile_pb2_grpc.ProfileServiceStub(channel)
            capability_stub = profile_pb2_grpc.CapabilityServiceStub(channel)

            profiles_resp = await profile_stub.ListProfiles(
                profile_pb2.ListProfilesRequest(), timeout=_CALL_TIMEOUT_S
            )
            match = next((p for p in profiles_resp.profiles if p.name == profile), None)
            if match is None:
                return []

            caps_resp = await capability_stub.ListCapabilities(
                profile_pb2.ListCapabilitiesRequest(), timeout=_CALL_TIMEOUT_S
            )
    except grpc.aio.AioRpcError as exc:
        _warn(f"profile server no disponible, catálogo vacío: {exc.details()}")
        return []
    except Exception as exc:  # noqa: BLE001 — cualquier otro fallo de red/canal
        _warn(f"profile server no disponible, catálogo vacío: {exc}")
        return []

    granted = set(match.capabilities)
    return sorted(
        (c for c in caps_resp.capabilities if c.id in granted),
        key=lambda c: c.id,
    )


async def get_capability_script(capability_id: str) -> tuple[str, str, dict[str, str]] | None:
    """Código fuente (base64) + lenguaje + helpers hermanos (filename -> base64,
    ver `Contract`/`Capability.extra_files`, ej. "_report_paths.py" para
    common.commit-report) de una capability. Best-effort: `None` ante
    cualquier fallo — igual criterio que `record_activity`, el caller decide
    cómo reaccionar (ver `dispatch`/`runner`).
    """
    try:
        async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
            stub = profile_pb2_grpc.CapabilityServiceStub(channel)
            resp = await stub.GetCapabilityScript(
                profile_pb2.GetCapabilityScriptRequest(id=capability_id), timeout=_CALL_TIMEOUT_S
            )
            return resp.source_code, resp.language, dict(resp.extra_files)
    except Exception as exc:  # noqa: BLE001
        _warn(f"no se pudo obtener el script de {capability_id}: {exc}")
        return None


async def profile_context(profile: str) -> tuple[profile_pb2.Profile, list[profile_pb2.Capability], list[profile_pb2.GovernanceRule]]:
    """Obtiene identidad, permisos efectivos y gobernanza del perfil activo."""
    if not profile:
        raise ValueError("no hay perfil activo")
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        profiles = profile_pb2_grpc.ProfileServiceStub(channel)
        capabilities = profile_pb2_grpc.CapabilityServiceStub(channel)
        governance = profile_pb2_grpc.GovernanceServiceStub(channel)
        listed = await profiles.ListProfiles(profile_pb2.ListProfilesRequest(), timeout=_CALL_TIMEOUT_S)
        selected = next((item for item in listed.profiles if item.name == profile), None)
        if selected is None:
            raise ValueError(f"el perfil {profile!r} no existe en el profile server")
        all_caps = await capabilities.ListCapabilities(profile_pb2.ListCapabilitiesRequest(), timeout=_CALL_TIMEOUT_S)
        granted = {item.id for item in all_caps.capabilities if item.id in set(selected.capabilities)}
        all_rules = await governance.ListRules(profile_pb2.ListRulesRequest(), timeout=_CALL_TIMEOUT_S)
        exceptions = await governance.ListExceptions(
            profile_pb2.ListExceptionsRequest(profile=profile, active_only=True), timeout=_CALL_TIMEOUT_S
        )
    excepted = {item.rule_id for item in exceptions.exceptions}
    rules = [
        item for item in all_rules.rules
        if item.id not in excepted and (item.source in {"global", profile} or item.capability in granted)
    ]
    return selected, sorted((item for item in all_caps.capabilities if item.id in granted), key=lambda item: item.id), sorted(rules, key=lambda item: item.id)


async def codex_rules(profile: str) -> tuple[list[profile_pb2.Capability], list[profile_pb2.GovernanceRule]]:
    """Compatibilidad para consumidores que sólo necesitan permisos y reglas."""
    _profile, capabilities, rules = await profile_context(profile)
    return capabilities, rules


async def hook_bundle(profile: str, assistant: str) -> tuple[list[profile_pb2.HookDefinition], dict[str, str], dict[str, str]]:
    """Hooks efectivos y sus fuentes para materializarlos en el proyecto.

    El filtrado de perfil/asistente/capability sucede en HookService: el MCP
    no replica esa política localmente.
    """
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        hooks_stub = profile_pb2_grpc.HookServiceStub(channel)
        response = await hooks_stub.ListHooks(
            profile_pb2.ListHooksRequest(profile=profile, assistant=assistant),
            timeout=_CALL_TIMEOUT_S,
        )
        hooks = list(response.hooks)
        scripts: dict[str, str] = {}
        for hook in hooks:
            source = await hooks_stub.GetHookScript(
                profile_pb2.GetHookScriptRequest(id=hook.id), timeout=_CALL_TIMEOUT_S
            )
            scripts[hook.id] = source.source_code
        shared = await hooks_stub.GetSharedHookAssets(
            profile_pb2.GetSharedHookAssetsRequest(), timeout=_CALL_TIMEOUT_S
        )
    return hooks, scripts, dict(shared.assets.files)


async def record_activity(
    *, capability_id: str, profile: str, status: str, summary: str = "", tags: list[str] | None = None
) -> None:
    """Registra la ejecución en el profile server. Best-effort: nunca levanta excepción."""
    try:
        async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
            stub = profile_pb2_grpc.ActivityServiceStub(channel)
            await stub.RecordActivity(
                profile_pb2.RecordActivityRequest(
                    capability_id=capability_id,
                    profile=profile or "",
                    status=status,
                    summary=summary,
                    tags=tags or [],
                ),
                timeout=_CALL_TIMEOUT_S,
            )
    except Exception as exc:  # noqa: BLE001 — profile server caído no debe tumbar el server MCP
        _warn(f"no se pudo registrar actividad en profile server: {exc}")
