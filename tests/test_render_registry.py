import hashlib
import json

from higpertext_mcp import render_registry


def test_record_render_persists_atomic_manifest_and_hashes(tmp_path):
    generated = tmp_path / "AGENTS.md"
    generated.write_text("generated\n", encoding="utf-8")

    record = render_registry.record_render(
        tmp_path,
        project_id="project-1",
        profile="dev",
        assistants=["codex"],
        result={"assistants": ["codex"], "files": ["AGENTS.md"], "removed": []},
    )

    manifest_path = tmp_path / record["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["render_id"] == record["render_id"]
    assert manifest["status"] == "success"
    assert manifest["written"] == ["AGENTS.md"]
    assert manifest["content_hashes"]["AGENTS.md"] == hashlib.sha256(b"generated\n").hexdigest()
    assert not list(manifest_path.parent.glob("*.tmp"))

    listed = render_registry.list_renders(tmp_path)
    assert listed[0]["render_id"] == record["render_id"]


def test_record_render_does_not_hash_paths_outside_project(tmp_path):
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")

    record = render_registry.record_render(
        tmp_path,
        project_id="project-1",
        profile="dev",
        assistants=["codex"],
        result={"files": [str(outside), "../outside-secret.txt"]},
    )

    manifest = json.loads((tmp_path / record["manifest"]).read_text(encoding="utf-8"))
    assert manifest["content_hashes"] == {}
