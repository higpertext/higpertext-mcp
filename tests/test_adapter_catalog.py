from higpertext_mcp import adapter_catalog, hook_protocol


def test_catalog_is_the_source_for_all_hook_protocols():
    assert tuple(hook_protocol.EVENTS) == adapter_catalog.SUPPORTED
    for assistant, spec in adapter_catalog.ADAPTERS.items():
        assert hook_protocol.EVENTS[assistant] == dict(spec.hook_events)
        assert hook_protocol.TOOLS[assistant] == dict(spec.tool_aliases)


def test_catalog_declares_feature_boundaries():
    assert adapter_catalog.assistants_with("skills") == (
        "claude", "codex", "gemini", "copilot", "antigravity", "opencode",
    )
    assert adapter_catalog.assistants_with("agents") == (
        "claude", "codex", "copilot", "opencode",
    )
    assert adapter_catalog.get("opencode").status == "bridge"
    assert adapter_catalog.get("antigravity").documentation_url == ""


def test_catalog_rejects_unknown_adapters():
    try:
        adapter_catalog.specs_for(["unknown"])
    except ValueError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("unknown adapter should be rejected")
