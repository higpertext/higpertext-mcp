from higpertext_mcp import dispatch


def test_params_to_argv_skips_none_values():
    argv = dispatch._params_to_argv("common.grep-search", {"pattern": "foo", "path": None})
    assert argv == ["common.grep-search", "--pattern", "foo"]


def test_params_to_argv_stringifies_values():
    argv = dispatch._params_to_argv("common.grep-search", {"max_results": 5})
    assert argv == ["common.grep-search", "--max_results", "5"]


def test_call_capability_real_grep_search_on_this_repo():
    """Requiere higpertext-cli instalado editable + correr desde un checkout real."""
    result = dispatch.call_capability(
        "common.grep-search",
        {"pattern": "def call_capability", "path": "src", "max_results": "5"},
    )
    assert result.ok
    assert "call_capability" in result.output
