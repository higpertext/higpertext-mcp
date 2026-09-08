"""Renderizadores autónomos de configuración para los asistentes soportados.

No importan ni ejecutan adapters de higpertext-cli. Los datos provienen del
profile server y los hooks se materializan por separado desde su catálogo.
"""
from __future__ import annotations

import json
from pathlib import Path

from higpertext_mcp.gen.profile.v1 import profile_pb2

SUPPORTED = ("codex", "claude", "gemini", "copilot", "antigravity", "opencode")
WORKFLOWS = {
    "build": """---
description: Implement approved changes in small, verifiable increments.
mode: primary
temperature: 0.2
permission:
  edit: allow
  bash: allow
---

# When to use

- After plan approval
- For concrete file changes in allowed scope

# Do

- Keep changes minimal and scoped
- Update docs/rules when source-of-truth moves
- Run validation commands relevant to changed artifacts

# Do not

- Expand scope beyond approved tasks
- Modify production PowerShell code when task is docs/agents-only
""",
    "compact": """---
description: Checkpoint and summarize agreements, resolved errors, and current code state before resetting history.
mode: primary
temperature: 0.1
permission:
  edit: allow
  bash: allow
---

# When to use

- After 15-20 messages discussing the same problem to avoid model confusion and save token costs.

# Do

- Summarize key decisions, current code state, resolved errors, and remaining task checklist.
- Persist learnings and state in the context memory (`.memory/context.md`).
- Instruct the user to use the `/compact` command (or clear chat history) while retaining the summary.

# Do not

- Lose active task agreements or historical context required for the current implementation.
""",
    "plan": """---
description: Analyze requested changes and produce safe, incremental implementation plans.
mode: primary
temperature: 0.1
permission:
  edit: deny
  bash: deny
---

# When to use

- At task intake for non-trivial work
- Before structural or cross-file changes
- After `/spec` produces an approved specification

# Do

- Before proposing a plan, consult the semantic graph with `common.graph-query`; if `.higpertext/state/semantic_graph.json` is missing, request/run `common.graph-rebuild` first.
- Use `.higpertext/state/semantic_graph.md/json` as the source of truth for modules, symbols, dependencies, and impact boundaries.
- Build stepwise implementation plans with rollback points.
- Identify unknowns and manual-verification points.
- After approval, write `.higpertext/roadmap.json` with phases and required skills.
- Each phase in `roadmap.json` must declare: `id`, `name`, `description`, `status` (`pending|active|done`), and `skills`.

# Do not

- Plan cross-file or structural changes without checking the semantic graph or explicitly reporting it unavailable.
- Modify files without an approved plan.
- Assume missing modules exist.
- Write `roadmap.json` before the user explicitly approves the plan.
""",
    "review": """---
description: Perform risk-oriented review of proposed or implemented changes against Clean Code, DDD, TDD, and best practices.
mode: primary
temperature: 0.1
permission:
  edit: deny
  bash: deny
---

# When to use

- Before merge or release tagging
- After structural changes across code, skills, or documentation

# Do

- Audit implementation against Clean Code principles.
- Verify DDD architecture integrity and repository abstractions.
- Verify TDD test coverage and quality, including happy and negative paths.
- Check compliance with SOLID, DRY, KISS, and YAGNI.
- Detect contract regressions, rule duplication, and documentation integrity issues.
- Flag unknown or planned references clearly.

# Do not

- Edit code or documentation directly during review.
- Approve a change without confirming complete coverage of the quality checklist.
""",
    "spec": """---
description: Generate and refine functional specifications through interactive assumptions clarification and BDD output.
mode: primary
temperature: 0.1
permission:
  edit: deny
  bash: deny
---

# When to use

- When the user asks to define, create, or refine a specification.
- When requirements arrive as a user story, spec draft, descriptive brief, or script path.

# Do

- Run the clarification workflow from `spec-clarification`.
- Produce an initial spec draft plus numbered functional assumptions.
- Ask rejected assumptions one by one, with progress.
- Confirm readiness before delivering the final specification.
- Deliver BDD scenarios and hand off to `plan` after approval.

# Do not

- Start implementation planning before the specification is confirmed.
- Skip the assumption-validation loop.
- Merge assumptions into requirements without explicit confirmation.
""",
}


def _rules(profile, caps: list, rules: list) -> str:
    """Instrucciones estables; las capabilities se descubren por MCP, no aquí."""
    name = getattr(profile, "name", profile)
    description = getattr(profile, "description", "")
    system_prompt = getattr(profile, "system_prompt", "")
    profile_rules = list(getattr(profile, "rules", []))
    lines = [f"# Perfil higpertext: {name}", ""]
    if description:
        lines += [description, ""]
    if system_prompt:
        lines += ["## Mandato del perfil", "", system_prompt, ""]
    lines += ["## Gobernanza efectiva", ""]
    lines += [f"- {rule}" for rule in profile_rules]
    lines += [f"- [{profile_pb2.Severity.Name(r.severity)}] **{r.id}** — {r.description}" for r in rules]
    if not rules and not profile_rules:
        lines.append("- No hay reglas de gobernanza activas para este perfil.")
    lines += [
        "", "## Descubrimiento y permisos", "",
        "- El servidor MCP es la fuente de verdad de capabilities disponibles y permisos efectivos.",
        "- Antes de elegir una capability, consulta las tools MCP disponibles en esta sesión.",
        "- Invoca sólo tools expuestas por el MCP; no infieras capabilities desde este archivo.",
        "- El servidor aplica el perfil activo y rechaza operaciones no autorizadas.", "",
    ]
    return "\n".join(lines)


def _write(path: Path, content: str, written: list[str], root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    written.append(str(path.relative_to(root)))


def _workflows(root: Path, base: Path, written: list[str]) -> None:
    # Solo los .md de referencia rápida (comandos tipo slash) — las skills
    # reales (SKILL.md) ya no salen de acá: las materializa skill_renderer.py
    # desde el catálogo de SkillService, no de este diccionario hardcodeado.
    for name, content in WORKFLOWS.items():
        _write(base / "workflows" / f"{name}.md", content, written, root)


def render(root: Path, assistants: list[str], profile, caps: list, rules: list) -> dict:
    invalid = sorted(set(assistants) - set(SUPPORTED))
    if invalid:
        raise ValueError(f"adapters no soportados: {', '.join(invalid)}")
    selected = list(dict.fromkeys(assistants)) or list(SUPPORTED)
    profile_name = getattr(profile, "name", profile)
    content = _rules(profile, caps, rules)
    written: list[str] = []
    for assistant in selected:
        if assistant == "codex":
            _write(root / "AGENTS.md", content, written, root)
            _write(root / ".codex" / "rules" / "higpertext_rules.md", content, written, root)
            for name in ("workflows",):
                (root / ".agents" / name).mkdir(parents=True, exist_ok=True)
            _workflows(root, root / ".agents", written)
            _write(root / ".agents" / "rules" / "higpertext_rules.md", content, written, root)
            _write(root / ".agents" / "mcp_config.json", json.dumps({"mcpServers": {"higpertext": {"type": "http", "url": "http://127.0.0.1:8790/mcp/"}}}, indent=2) + "\n", written, root)
        elif assistant == "claude":
            _write(root / ".claude" / "rules" / f"{profile_name}.md", content, written, root)
            _write(root / "CLAUDE.md", f"# {profile_name}\n\nVer `.claude/rules/{profile_name}.md`.\n", written, root)
            _write(root / ".clauderules", content, written, root)
        elif assistant == "gemini":
            _write(root / "GEMINI.md", content, written, root)
            for name in ("workflows",):
                (root / ".gemini" / name).mkdir(parents=True, exist_ok=True)
            _workflows(root, root / ".gemini", written)
        elif assistant == "copilot":
            _write(root / ".github" / "copilot-instructions.md", content, written, root)
            _write(root / "AGENTS.md", f"# {profile}\n\nVer `.github/copilot-instructions.md`.\n", written, root)
        elif assistant == "antigravity":
            _write(root / "AGENTS.md", content, written, root)
            _write(root / ".agents" / "rules" / "higpertext_rules.md", content, written, root)
            _write(root / ".agents" / "settings.json", json.dumps({"mcp": "higpertext", "profile": profile_name}, indent=2) + "\n", written, root)
            _workflows(root, root / ".agents", written)
        elif assistant == "opencode":
            _write(root / ".opencode" / "rules" / f"{profile_name}.md", content, written, root)
            _write(root / "AGENTS.md", f"# {profile_name}\n\nVer `.opencode/rules/{profile_name}.md`.\n", written, root)
            _write(root / "opencode.json", json.dumps({"instructions": ["AGENTS.md", ".opencode/rules/*.md"], "mcp": {"higpertext": {"type": "remote", "url": "http://127.0.0.1:8790/mcp/"}}}, indent=2) + "\n", written, root)
    return {"assistants": selected, "files": written, "capabilities": len(caps), "rules": len(rules)}
