import asyncio
import json
from pathlib import Path

from higpertext_mcp import adapter_renderer, hook_runner
from higpertext_mcp.gen.profile.v1 import profile_pb2


def _rule(rule_id: str, enabled: bool | None, source: str = "global", pattern: str = "blocked"):
    rule = profile_pb2.GovernanceRule(
        id=rule_id, description=f"Description {rule_id}", severity=profile_pb2.HIGH,
        source=source, pattern=pattern,
    )
    if enabled is not None:
        rule.enabled = enabled
    return rule

def test_profile_rule_rendering_skips_disabled_rules(monkeypatch):
    rules = [
        _rule("global-on", True),
        _rule("profile-on", True, "dev"),
        _rule("profile-off", False, "dev"),
        _rule("legacy", None, "dev"),
        _rule("other-profile", True, "other"),
        _rule("off-pattern", False, "dev", pattern=""),
    ]

    async def effective_profile(_root: Path):
        return "dev"

    async def list_rules():
        return rules

    monkeypatch.setattr(hook_runner.discovery, "effective_profile", effective_profile)
    monkeypatch.setattr(hook_runner.profile_client, "list_governance_rules", list_rules)

    rendered = json.loads(asyncio.run(hook_runner._render_profile_rules(Path("/project"))))
    assert [entry["pattern"] for entry in rendered["rules"]] == ["blocked", "blocked", "blocked"]
    assert [entry["reason"] for entry in rendered["rules"]] == ["Description global-on", "Description profile-on", "Description legacy"]

def test_adapter_rules_document_skips_disabled_rules():
    profile = profile_pb2.Profile(name="dev")
    rendered = adapter_renderer._rules(profile, [], [_rule("on", True), _rule("off", False)])
    assert "**on**" in rendered
    assert "**off**" not in rendered
