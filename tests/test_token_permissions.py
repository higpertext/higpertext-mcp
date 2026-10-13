from higpertext_mcp.http_auth import ApiTokenContext
from higpertext_mcp.token_permissions import required_permission, tool_allowed


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
