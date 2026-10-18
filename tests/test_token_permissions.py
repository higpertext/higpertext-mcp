import pytest

from higpertext_mcp.http_auth import ApiTokenContext
from higpertext_mcp.token_permissions import required_permission, resource_allowed, tool_allowed


def token(*scopes: str) -> ApiTokenContext:
    return ApiTokenContext("t", "u", frozenset(scopes), "", frozenset(), frozenset())


def test_board_verification_actions_use_existing_board_scopes():
    assert required_permission("higpertext-roadmap-board", "task_propose_scenarios") == "boards.advance"
    assert required_permission("higpertext-roadmap-board", "task_freeze_spec") == "boards.advance"
    assert required_permission("higpertext-roadmap-board", "verification_runs") == "boards.view"
    assert required_permission("higpertext-roadmap-board", "activity_gate") == "boards.view"
    assert tool_allowed("higpertext-roadmap-board", token("boards.advance"), action="task_propose_scenarios")
    assert not tool_allowed("higpertext-roadmap-board", token("boards.view"), action="task_propose_scenarios")
    assert tool_allowed("higpertext-roadmap-board", token("boards.view"), action="activity_gate")


@pytest.mark.anyio
async def test_single_org_token_implies_org_for_global_calls():
    single_org = ApiTokenContext(
        "t", "u", frozenset({"boards.view"}), "", frozenset({"org-a"}), frozenset(),
    )
    # Llamada global sin organization_id (ej. common-roadmap-board-status con solo board_name).
    assert await resource_allowed(single_org, {"board_name": "Roadmap principal"}, "common.roadmap-board-status")
    # Con proyecto, la organización sigue siendo explícita.
    assert not await resource_allowed(single_org, {"project_id": "project-a"}, "common.roadmap-board-status")
    # La tool local higpertext-roadmap-board sigue exigiendo organization_id explícito.
    assert not await resource_allowed(
        single_org, {"action": "overview"}, "", "higpertext-roadmap-board",
    )


@pytest.mark.anyio
async def test_multi_org_token_still_requires_explicit_org():
    multi_org = ApiTokenContext(
        "t", "u", frozenset({"boards.view"}), "", frozenset({"org-a", "org-b"}), frozenset(),
    )
    assert not await resource_allowed(multi_org, {"board_name": "Roadmap principal"}, "common.roadmap-board-status")


@pytest.mark.anyio
async def test_org_and_project_scope_fail_closed():
    org_token = ApiTokenContext(
        "t", "u", frozenset({"projects.view"}), "",
        frozenset({"org-a"}), frozenset(), frozenset({"project-a"}),
        {"org-a": frozenset({"project-a"})},
    )
    assert await resource_allowed(org_token, {"organization_id": "org-a"})
    assert not await resource_allowed(org_token, {"organization_id": "org-b"})
    assert await resource_allowed(org_token, {"organization_id": "org-a", "project_id": "project-a"})
    assert not await resource_allowed(org_token, {"project_id": "project-a"})
    assert not await resource_allowed(org_token, {"organization_id": "org-b", "project_id": "project-a"})
    assert not await resource_allowed(org_token, {"project_id": "project-b"})
    assert not await resource_allowed(
        ApiTokenContext("t", "u", frozenset(), "", frozenset({"org-a"}), frozenset()),
        {"project_id": "project-b"},
    )


@pytest.mark.anyio
async def test_org_scoped_pat_allows_its_project():
    scoped = ApiTokenContext(
        "t", "u", frozenset({"projects.view"}), "",
        frozenset({"org-a"}), frozenset(), frozenset({"project-a"}),
        {"org-a": frozenset({"project-a"})},
    )
    assert await resource_allowed(scoped, {"organization_id": "org-a", "project_id": "project-a"})


@pytest.mark.anyio
async def test_org_scoped_pat_rejects_other_tenants_and_unscoped_resources():
    scoped = ApiTokenContext(
        "t", "u", frozenset({"projects.view"}), "",
        frozenset({"org-a"}), frozenset(), frozenset({"project-a"}),
        {"org-a": frozenset({"project-a"})},
    )
    assert not await resource_allowed(scoped, {"organization_id": "org-b"})
    assert not await resource_allowed(scoped, {"project_id": "project-a"})
    assert not await resource_allowed(scoped, {"organization_id": "org-b", "project_id": "project-a"})
    assert not await resource_allowed(scoped, {"organization_id": "org-a", "project_id": "project-b"})
