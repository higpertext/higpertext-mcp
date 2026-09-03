---
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
- After /spec produces an approved specification

# Do

- Before proposing a plan, consult the semantic graph with common.graph-query for the relevant symbols; if .higpertext/state/semantic_graph.json is missing, request/run common.graph-rebuild first
- Use .higpertext/state/semantic_graph.md/json as the source of truth for existing modules, symbols, dependencies, and impact boundaries
- Build stepwise implementation plans with rollback points
- Identify unknowns and manual-verification points
- Map requested scope to skills and sub-agents
- Multiple roadmaps can be active at once (multi-agent workspace) — pick a short kebab-case <roadmap-id> that uniquely names THIS objective; do not reuse another roadmap's id or merge unrelated objectives into one file
- After the user approves the plan, scaffold the roadmap through the real CLI, not by hand-writing JSON: run `htx roadmap new <roadmap-id> --project <roadmap-id> --description "<one-line goal>"` — this creates .higpertext/config/roadmaps/<roadmap-id>.json via the governed path
- Edit the scaffolded file to add the fields `htx roadmap new` does not fill in: top-level `id` and `name` (required by the roadmap-report generator), the `phases[]` array, and `session_resources`
- Register the roadmap as active through the CLI: run `htx roadmap add <roadmap-id>` — do not hand-edit active.json directly
- Each phase in the roadmap file must declare: id, name, description, status (pending|active|done), skills[], subagents[]
- Aggregate all unique skills and subagents across phases into session_resources.skills[] and session_resources.subagents[]
- When a roadmap's objective is fully delivered, set every phase to status=done and run `htx roadmap remove <roadmap-id>` — the file stays on disk as a historical record but stops mounting its session_resources
- For traceability, any test/harness file created to satisfy a phase should reference its roadmap id and phase id in a short header comment (e.g. "Roadmap: hooks-harness / phase-1")

# Do not

- Plan cross-file or structural changes without first checking the semantic graph or explicitly reporting that it is unavailable
- Modify files without an approved plan
- Assume missing modules exist
- Write the roadmap file before the user explicitly approves the plan
- Include skills or subagents that have no template in src/core/templates/
- use .higpertext/config/roadmaps/<roadmap-id>.json instead
- Hand-write a brand-new roadmap JSON from scratch, or hand-edit active.json directly — use `htx roadmap new`/`add`/`remove` so every roadmap is created through the same governed, validated path

## Active skills

- [higpertext-guide](file:///.agents/skills/higpertext-guide/SKILL.md)

## Active subagents

- `research`

# Session Info
- **Session ID**: `sess_1788344422_d70a`
- **Status**: `active`