"""Mapeo de herramientas MCP a permisos de tokens emitidos por rules-api."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from higpertext_mcp.http_auth import ApiTokenContext

_READ_ACTIONS = {"get", "list", "list_global", "get_shared_assets", "overview", "list_boards", "status"}
_GOVERNANCE_TOOLS = {
    "higpertext-governance-rule", "higpertext-governance-exception",
    "higpertext-profile", "higpertext-capability", "higpertext-hook-admin",
    "higpertext-skill", "higpertext-agent",
}


def has_permission(context: ApiTokenContext, permission: str) -> bool:
    scopes = context.scopes
    if permission in scopes or "administración" in scopes:
        return True
    if permission.endswith(".view") and "lectura" in scopes:
        return True
    if permission == "governance.edit" and "hooks" in scopes:
        return True
    if permission == "workflows.run" and "workflows" in scopes:
        return True
    return False


def required_permission(tool_name: str, action: str = "", capability_id: str = "") -> str | None:
    if capability_id:
        return f"mcp:capability:{capability_id}:action:{action or 'invoke'}"
    if tool_name in {"higpertext-configure-project", "higpertext-render-adapters"}:
        return "projects.edit"
    if tool_name == "higpertext-system-overview":
        return "projects.view"
    if tool_name == "higpertext-telemetry-session-bind":
        return "telemetry.session.bind"
    if tool_name == "higpertext-roadmap-board":
        if action in {"overview", "list_boards"}:
            return "boards.view"
        if action in {"move", "task_update", "task_propose_scenarios", "task_freeze_spec"}:
            return "boards.advance"
        if action in {"verification_runs", "activity_gate"}:
            return "boards.view"
        return "boards.edit" if action else "boards.view"
    if tool_name in _GOVERNANCE_TOOLS:
        return "governance.view" if action in _READ_ACTIONS else "governance.edit"
    if tool_name.startswith("external."):
        return "governance.edit"
    return None


def tool_allowed(
    tool_name: str,
    scopes: ApiTokenContext,
    capability_id: str = "",
    action: str = "",
    capability_permissions: list[dict[str, str]] | None = None,
    resource_id: str = "",
) -> bool:
    if capability_id:
        permissions = capability_permissions or []
        permission_actions = {item.get("action", "") for item in permissions}
        # No metadata means deny new PAT grants; tokens created with the old
        # blanket execute scope retain their previously granted access.
        operation = action or "invoke"
        legacy_scope = f"mcp:capability:{capability_id}:execute" in scopes.scopes
        invoke_scope = f"mcp:capability:{capability_id}:action:invoke"
        if "invoke" in permission_actions and has_permission(scopes, invoke_scope):
            return True
        if operation not in permission_actions and not legacy_scope and "administración" not in scopes.scopes:
            return False
        return has_permission(scopes, f"mcp:capability:{capability_id}:action:{operation}") or (
            legacy_scope
        )
    if tool_name == "higpertext-skill":
        read_scope = f"mcp:skill:{resource_id}:read" if resource_id else ""
        write_scope = f"mcp:skill:{resource_id}:write" if resource_id else ""
        has_any_skill_scope = any(
            scope.startswith("mcp:skill:") and scope.endswith(":read")
            for scope in scopes.scopes
        )
        has_any_skill_write_scope = any(
            scope.startswith("mcp:skill:") and scope.endswith(":write")
            for scope in scopes.scopes
        )
        if action == "get" and ((read_scope and has_permission(scopes, read_scope)) or (not resource_id and has_any_skill_scope)):
            return True
        if action in {"update", "delete"} and ((write_scope and has_permission(scopes, write_scope)) or (not resource_id and has_any_skill_write_scope)):
            return True
    permission = required_permission(tool_name, action, capability_id)
    return permission is not None and has_permission(scopes, permission)


def filtered_tool(
    tool: Any,
    context: ApiTokenContext,
    capability_id: str = "",
    capability_permissions: list[dict[str, str]] | None = None,
) -> Any | None:
    """Oculta tools sin alcance y retira acciones no autorizadas de su schema."""
    action_schema = (tool.inputSchema.get("properties") or {}).get("action", {})
    actions = action_schema.get("enum") if isinstance(action_schema, dict) else None
    if capability_id and capability_permissions:
        properties = tool.inputSchema.get("properties") or {}
        action_property = properties.get("action")
        permission_actions = [str(item.get("action", "")) for item in capability_permissions]
        # Older capability schemas often describe valid actions in prose but
        # omit enum_values. Publish the declared permission actions as the
        # schema enum, then expose only the ones granted by this PAT.
        if isinstance(action_property, dict) and "invoke" not in permission_actions:
            declared_actions = list(actions) if actions else permission_actions
            allowed = [
                action for action in declared_actions
                if tool_allowed(tool.name, context, capability_id, str(action), capability_permissions)
            ]
            if not allowed:
                return None
            result = deepcopy(tool)
            result.inputSchema["properties"]["action"]["enum"] = allowed
            return result
    if actions:
        allowed = [
            action for action in actions
            if tool_allowed(tool.name, context, capability_id, str(action), capability_permissions)
        ]
        if not allowed:
            return None
        result = deepcopy(tool)
        result.inputSchema["properties"]["action"]["enum"] = allowed
        return result
    return tool if tool_allowed(tool.name, context, capability_id, capability_permissions=capability_permissions) else None


_PROJECT_TOOLS = {
    "higpertext-configure-project", "higpertext-render-adapters",
    "higpertext-roadmap-board", "higpertext-system-overview",
    "higpertext-telemetry-session-bind",
}


async def resource_allowed(
    context: ApiTokenContext, arguments: dict[str, Any], capability_id: str = "", tool_name: str = ""
) -> bool:
    """Aplica los límites de repositorio del PAT al proyecto de la solicitud."""
    if not context.repository_ids:
        return True
    if not capability_id and tool_name not in _PROJECT_TOOLS and not tool_name.startswith("external."):
        return True
    repository_id = str(arguments.get("repository_id", ""))
    if repository_id:
        return repository_id in context.repository_ids
    try:
        from higpertext_mcp import discovery, profile_client

        project_id = str(arguments.get("project_id", ""))
        root_path = str(arguments.get("root_path", ""))
        if project_id:
            project = next(
                (p for p in await profile_client.list_projects() if p.get("id") == project_id), None
            )
            if project is None:
                return False
        elif root_path:
            _, project = await discovery.resolve_registered_project(root_path=root_path)
        else:
            root = discovery.resolve_project_root()
            project = await profile_client.resolve_project(str(root))
        repositories = await profile_client.list_repositories()
        return any(
            repo.get("id") in context.repository_ids
            and repo.get("project_id") == project.get("id")
            for repo in repositories
        )
    except (OSError, RuntimeError, ValueError, KeyError):
        return False
