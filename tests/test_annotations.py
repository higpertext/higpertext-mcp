from higpertext_mcp import annotations


def test_read_only_capability_hints():
    hints = annotations.hints_for("common.grep-search")
    assert hints.read_only is True
    assert hints.destructive is False
    assert hints.idempotent is True


def test_destructive_capability_hints():
    hints = annotations.hints_for("common.quality-resolver")
    assert hints.read_only is False
    assert hints.destructive is True


def test_mutating_non_destructive_capability_hints():
    hints = annotations.hints_for("git.committer")
    assert hints.read_only is False
    assert hints.destructive is False
    assert hints.idempotent is False


def test_unknown_capability_defaults_to_conservative_hints():
    hints = annotations.hints_for("common.something-new")
    assert hints.read_only is False
    assert hints.destructive is False
    assert hints.idempotent is False
