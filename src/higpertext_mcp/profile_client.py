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


async def get_hook_script(hook_id: str) -> str | None:
    """Código fuente (base64) de un hook. Best-effort: `None` ante cualquier
    fallo, mismo criterio que `get_capability_script`."""
    try:
        async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
            stub = profile_pb2_grpc.HookServiceStub(channel)
            resp = await stub.GetHookScript(
                profile_pb2.GetHookScriptRequest(id=hook_id), timeout=_CALL_TIMEOUT_S
            )
            return resp.source_code
    except Exception as exc:  # noqa: BLE001
        _warn(f"no se pudo obtener el script del hook {hook_id}: {exc}")
        return None


async def get_shared_hook_assets() -> dict[str, str]:
    """Dependencias compartidas por todos los hooks (hook_utils.py, hook_io.py,
    _rules/*) — filename (puede incluir subdirectorio) -> source (base64)."""
    try:
        async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
            stub = profile_pb2_grpc.HookServiceStub(channel)
            resp = await stub.GetSharedHookAssets(
                profile_pb2.GetSharedHookAssetsRequest(), timeout=_CALL_TIMEOUT_S
            )
            return dict(resp.assets.files)
    except Exception as exc:  # noqa: BLE001
        _warn(f"no se pudieron obtener los shared hook assets: {exc}")
        return {}


async def set_shared_hook_assets(files: dict[str, str]) -> dict[str, str]:
    """Reemplaza el bundle entero de dependencias compartidas por hooks
    (hook_utils.py, hook_io.py, _rules/*) — `files` en texto plano (filename,
    puede incluir subdirectorio como '_rules/bash_rules.py' -> contenido);
    el base64 lo hace esta función, no le corresponde al caller. SetSharedHookAssets
    pisa el bundle anterior entero, no hace merge — si querés conservar un
    archivo existente, primero traelo con get_shared_hook_assets."""
    import base64

    encoded = {k: base64.b64encode(v.encode("utf-8")).decode("ascii") for k, v in files.items()}
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.HookServiceStub(channel)
        resp = await stub.SetSharedHookAssets(profile_pb2.SetSharedHookAssetsRequest(files=encoded), timeout=_CALL_TIMEOUT_S)
        return dict(resp.assets.files)


def _hook_to_dict(h: profile_pb2.HookDefinition) -> dict:
    return {
        "id": h.id, "event": h.event, "matcher": h.matcher, "script": h.script,
        "description": h.description, "timeout": h.timeout, "enabled": h.enabled,
        "assistants": list(h.assistants), "profiles": list(h.profiles),
        "capability_id": h.capability_id, "priority": h.priority,
    }


async def create_hook(
    *, id: str, event: str, source_code: str, matcher: str = "", description: str = "",
    timeout: int = 10, enabled: bool = True, assistants: list[str] | None = None,
    profiles: list[str] | None = None, capability_id: str = "", priority: int = 0,
    script: str = "",
) -> dict:
    """Da de alta un hook — el `id` que hooks.json/settings.json referencian
    como `higpertext-hook <id>`. `source_code` en texto plano (el base64 lo
    hace esta función). `script` es solo metadata/label, no se lee de ningún
    disco en runtime."""
    import base64

    req = profile_pb2.CreateHookRequest(
        id=id, event=event, matcher=matcher, script=script or f"{id}.py", description=description,
        timeout=timeout, enabled=enabled, assistants=assistants or [], profiles=profiles or [],
        capability_id=capability_id, priority=priority,
        source_code=base64.b64encode(source_code.encode("utf-8")).decode("ascii"),
    )
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.HookServiceStub(channel)
        resp = await stub.CreateHook(req, timeout=_CALL_TIMEOUT_S)
        return _hook_to_dict(resp.hook)


async def get_hook(hook_id: str) -> dict:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.HookServiceStub(channel)
        resp = await stub.GetHook(profile_pb2.GetHookRequest(id=hook_id), timeout=_CALL_TIMEOUT_S)
        return _hook_to_dict(resp.hook)


async def list_hooks_raw() -> list[dict]:
    """Catálogo completo de hooks (sin filtrar por perfil/asistente) — para
    administración, a diferencia de `list_hooks` que sí filtra (usado por
    hook_renderer.py)."""
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.HookServiceStub(channel)
        resp = await stub.ListHooks(profile_pb2.ListHooksRequest(), timeout=_CALL_TIMEOUT_S)
        return [_hook_to_dict(h) for h in resp.hooks]


async def delete_hook(hook_id: str) -> None:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.HookServiceStub(channel)
        await stub.DeleteHook(profile_pb2.DeleteHookRequest(id=hook_id), timeout=_CALL_TIMEOUT_S)


def _profile_to_dict(p: profile_pb2.Profile) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "system_prompt": p.system_prompt,
        "capabilities": list(p.capabilities),
        "subprofiles": list(p.subprofiles),
        "rules": list(p.rules),
        "hooks_global": list(p.hooks_global),
    }


async def create_profile(
    *, name: str, description: str = "", system_prompt: str = "",
    capabilities: list[str] | None = None, subprofiles: list[str] | None = None,
    rules: list[str] | None = None, hooks_global: list[str] | None = None,
) -> dict:
    """Crea un Profile — un "agente": nombre, system prompt, y qué capabilities/
    hooks/subprofiles/reglas tiene habilitados. Deja que errores gRPC (nombre
    duplicado, etc.) se propaguen al caller."""
    req = profile_pb2.CreateProfileRequest(
        name=name, description=description, system_prompt=system_prompt,
        capabilities=capabilities or [], subprofiles=subprofiles or [],
        rules=rules or [], hooks_global=hooks_global or [],
    )
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.ProfileServiceStub(channel)
        resp = await stub.CreateProfile(req, timeout=_CALL_TIMEOUT_S)
        return _profile_to_dict(resp.profile)


async def _resolve_profile(channel, id_or_name: str) -> profile_pb2.Profile:
    """GetProfile busca por id (UUID interno) — un caller normalmente solo
    conoce el `name` (slug) que le dio a create_profile, así que si el intento
    directo por id falla, se cae a ListProfiles+filtro por name, mismo
    criterio que usa render-hooks del lado Go."""
    stub = profile_pb2_grpc.ProfileServiceStub(channel)
    try:
        resp = await stub.GetProfile(profile_pb2.GetProfileRequest(id=id_or_name), timeout=_CALL_TIMEOUT_S)
        return resp.profile
    except grpc.aio.AioRpcError as exc:
        if exc.code() != grpc.StatusCode.NOT_FOUND:
            raise
    resp = await stub.ListProfiles(profile_pb2.ListProfilesRequest(), timeout=_CALL_TIMEOUT_S)
    match = next((p for p in resp.profiles if p.name == id_or_name), None)
    if match is None:
        raise LookupError(f"no existe ningún profile con id o name {id_or_name!r}")
    return match


async def get_profile(profile_id: str) -> dict:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        return _profile_to_dict(await _resolve_profile(channel, profile_id))


async def list_profiles() -> list[dict]:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.ProfileServiceStub(channel)
        resp = await stub.ListProfiles(profile_pb2.ListProfilesRequest(), timeout=_CALL_TIMEOUT_S)
        return [_profile_to_dict(p) for p in resp.profiles]


async def update_profile(
    *, id: str, name: str = "", description: str = "", system_prompt: str = "",
    capabilities: list[str] | None = None, subprofiles: list[str] | None = None,
    rules: list[str] | None = None, hooks_global: list[str] | None = None,
) -> dict:
    """Reemplaza el Profile entero (no hace merge parcial — mandá todos los
    campos que querés preservar, no solo el que cambia). `id` acepta el name
    también (ver `_resolve_profile`)."""
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        current = await _resolve_profile(channel, id)
        req = profile_pb2.UpdateProfileRequest(
            id=current.id, name=name or current.name, description=description, system_prompt=system_prompt,
            capabilities=capabilities or [], subprofiles=subprofiles or [],
            rules=rules or [], hooks_global=hooks_global or [],
        )
        stub = profile_pb2_grpc.ProfileServiceStub(channel)
        resp = await stub.UpdateProfile(req, timeout=_CALL_TIMEOUT_S)
        return _profile_to_dict(resp.profile)


async def delete_profile(profile_id: str) -> None:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        current = await _resolve_profile(channel, profile_id)
        stub = profile_pb2_grpc.ProfileServiceStub(channel)
        await stub.DeleteProfile(profile_pb2.DeleteProfileRequest(id=current.id), timeout=_CALL_TIMEOUT_S)


def _capability_to_dict(c: profile_pb2.Capability) -> dict:
    return {
        "id": c.id,
        "version": c.version,
        "name": c.name,
        "description": c.description,
        "entrypoint": c.entrypoint,
        "language": c.language,
        "parameters": [
            {"name": p.name, "type": p.type, "required": p.required, "description": p.description, "default": p.default}
            for p in c.parameters
        ],
        "requires_pat": c.requires_pat,
        "hook_task_id": c.hook_task_id,
        "contract": {"rules": list(c.contract.rules), "success_pattern": c.contract.success_pattern, "on_empty": c.contract.on_empty},
    }


async def create_capability(
    *, id: str, entrypoint: str, source_code: str, name: str = "", description: str = "",
    version: str = "1.0.0", language: str = "python", parameters: list[dict] | None = None,
    requires_pat: bool = False, hook_task_id: str = "", contract: dict | None = None,
    extra_files: dict[str, str] | None = None,
) -> dict:
    """Da de alta una capability nueva — el "backend" real que una capability
    ejecuta. `source_code` y los valores de `extra_files` van en texto plano
    (el encoding a base64 que pide el proto se hace acá, no le corresponde al
    caller armarlo a mano). `entrypoint` es el path relativo bajo el que el
    engine identifica el script (ej. "capabilities/custom/scripts/my_tool.py"),
    usado solo como metadata/nombre de archivo — no se lee del disco.
    """
    import base64

    params = [
        profile_pb2.Parameter(
            name=p.get("name", ""), type=p.get("type", "string"), required=bool(p.get("required", False)),
            description=p.get("description", ""), default=str(p["default"]) if p.get("default") is not None else "",
        )
        for p in (parameters or [])
    ]
    contract_msg = profile_pb2.Contract(
        rules=(contract or {}).get("rules", []),
        success_pattern=(contract or {}).get("success_pattern", ""),
        on_empty=(contract or {}).get("on_empty", ""),
    )
    req = profile_pb2.CreateCapabilityRequest(
        id=id, version=version, name=name or id, description=description, entrypoint=entrypoint,
        language=language, parameters=params, requires_pat=requires_pat, hook_task_id=hook_task_id,
        contract=contract_msg, source_code=base64.b64encode(source_code.encode("utf-8")).decode("ascii"),
        extra_files={k: base64.b64encode(v.encode("utf-8")).decode("ascii") for k, v in (extra_files or {}).items()},
    )
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.CapabilityServiceStub(channel)
        resp = await stub.CreateCapability(req, timeout=_CALL_TIMEOUT_S)
        return _capability_to_dict(resp.capability)


async def get_capability(capability_id: str) -> dict:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.CapabilityServiceStub(channel)
        resp = await stub.GetCapability(profile_pb2.GetCapabilityRequest(id=capability_id), timeout=_CALL_TIMEOUT_S)
        return _capability_to_dict(resp.capability)


async def list_capabilities_raw() -> list[dict]:
    """A diferencia de `list_allowed_capabilities`, no filtra por perfil — el
    catálogo completo, para administración (editar/borrar cualquier capability
    exista o no en el perfil activo)."""
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.CapabilityServiceStub(channel)
        resp = await stub.ListCapabilities(profile_pb2.ListCapabilitiesRequest(), timeout=_CALL_TIMEOUT_S)
        return [_capability_to_dict(c) for c in resp.capabilities]


async def delete_capability(capability_id: str) -> None:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.CapabilityServiceStub(channel)
        await stub.DeleteCapability(profile_pb2.DeleteCapabilityRequest(id=capability_id), timeout=_CALL_TIMEOUT_S)


async def create_governance_rule(
    *,
    id: str,
    description: str,
    severity: str,
    scopes: list[str],
    source: str = "global",
    capability: str = "",
    automated: bool = False,
    numeric_threshold: float | None = None,
    pattern: str = "",
) -> profile_pb2.GovernanceRule:
    """Da de alta una regla de gobernanza. Si `pattern` no está vacío, la
    regla también aplica en runtime: hook_bash_guard.check_profile_rules la
    evalúa como regex contra cada comando Bash (ver hooks-src). Deja que
    cualquier error gRPC (id duplicado, severity/scope inválido) se propague
    — el caller (tool handler en server.py) es quien decide cómo reportarlo,
    no hay fallback silencioso para una escritura explícita como esta."""
    req = profile_pb2.CreateRuleRequest(
        id=id,
        description=description,
        severity=profile_pb2.Severity.Value(severity.upper()),
        scopes=[profile_pb2.Scope.Value(s.upper()) for s in scopes],
        automated=automated,
        capability=capability,
        source=source,
        pattern=pattern,
    )
    if numeric_threshold is not None:
        req.numeric_threshold = numeric_threshold
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.GovernanceServiceStub(channel)
        resp = await stub.CreateRule(req, timeout=_CALL_TIMEOUT_S)
        return resp.rule


async def list_governance_rules(scope: str = "") -> list[profile_pb2.GovernanceRule]:
    req = profile_pb2.ListRulesRequest()
    if scope:
        req.scope = profile_pb2.Scope.Value(scope.upper())
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.GovernanceServiceStub(channel)
        resp = await stub.ListRules(req, timeout=_CALL_TIMEOUT_S)
        return list(resp.rules)


async def delete_governance_rule(rule_id: str) -> None:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.GovernanceServiceStub(channel)
        await stub.DeleteRule(profile_pb2.DeleteRuleRequest(id=rule_id), timeout=_CALL_TIMEOUT_S)


def _exception_to_dict(e: profile_pb2.GovernanceException) -> dict:
    return {"id": e.id, "rule_id": e.rule_id, "reason": e.reason, "approver": e.approver, "profile": e.profile, "expires": e.expires if e.HasField("expires") else None}


async def create_governance_exception(*, rule_id: str, reason: str, approver: str, profile: str = "", expires: str | None = None) -> dict:
    """Aprueba una excepción puntual a una regla de gobernanza (ej. mientras se
    resuelve una deuda técnica). `expires` en formato YYYY-MM-DD, opcional."""
    req = profile_pb2.CreateExceptionRequest(rule_id=rule_id, reason=reason, approver=approver, profile=profile)
    if expires is not None:
        req.expires = expires
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.GovernanceServiceStub(channel)
        resp = await stub.CreateException(req, timeout=_CALL_TIMEOUT_S)
        return _exception_to_dict(resp.exception)


async def list_governance_exceptions(*, profile: str = "", active_only: bool = False) -> list[dict]:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.GovernanceServiceStub(channel)
        resp = await stub.ListExceptions(profile_pb2.ListExceptionsRequest(profile=profile, active_only=active_only), timeout=_CALL_TIMEOUT_S)
        return [_exception_to_dict(e) for e in resp.exceptions]


async def delete_governance_exception(exception_id: str) -> None:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.GovernanceServiceStub(channel)
        await stub.DeleteException(profile_pb2.DeleteExceptionRequest(id=exception_id), timeout=_CALL_TIMEOUT_S)


def _skill_to_dict(s: profile_pb2.Skill) -> dict:
    return {"id": s.id, "name": s.name, "description": s.description, "content": s.content, "version": s.version, "enabled": s.enabled}


async def list_skills(*, enabled_only: bool = False) -> list[dict]:
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        stub = profile_pb2_grpc.SkillServiceStub(channel)
        resp = await stub.ListSkills(profile_pb2.ListSkillsRequest(enabled_only=enabled_only), timeout=_CALL_TIMEOUT_S)
        return [_skill_to_dict(s) for s in resp.skills]


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


async def list_hooks(profile: str, assistant: str) -> list[profile_pb2.HookDefinition]:
    """Hooks efectivos para un perfil+asistente — solo metadata (event/matcher/
    timeout/description), sin el source_code: el wiring nativo generado solo
    referencia `higpertext-hook <id>` (ver hook_renderer.py), el script real
    se resuelve en runtime vía `get_hook_script`/`get_shared_hook_assets`.

    El filtrado de perfil/asistente/capability sucede en HookService: el MCP
    no replica esa política localmente.
    """
    async with grpc.aio.insecure_channel(config.profile_server_addr()) as channel:
        hooks_stub = profile_pb2_grpc.HookServiceStub(channel)
        response = await hooks_stub.ListHooks(
            profile_pb2.ListHooksRequest(profile=profile, assistant=assistant),
            timeout=_CALL_TIMEOUT_S,
        )
        return list(response.hooks)


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
