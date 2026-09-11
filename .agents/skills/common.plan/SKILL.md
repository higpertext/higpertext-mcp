---
name: common.plan
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

- Before proposing a plan, consult the semantic graph with `common.graph-query`.
- The semantic graph is persisted in Redis and must be queried through the MCP capability; do not treat `.higpertext/state/semantic_graph.json` or a Markdown export as the source of truth.
- If the graph key is missing or Redis is unavailable, run `common.graph-rebuild` with the project root and report the failure explicitly if rebuild cannot complete.
- Use a root path consistent between `common.graph-rebuild` and `common.graph-query`; the Redis key is derived from that root.
- Query a real symbol or module name relevant to the task and distinguish `[NOT FOUND]` for an unmatched keyword from a missing/failed graph.
- After profile or capability changes, verify the persisted profile with `higpertext-profile get`. The current session's tool list may be stale; if a required capability is absent from the exposed tools, refresh/restart the MCP session before claiming it is unavailable.
- For graph or capability changes, confirm runtime state with `common.server-verification-report` and record warnings when metrics, Redis, or hook-cache evidence is unavailable.
- Build stepwise implementation plans with rollback points.
- Identify unknowns and manual-verification points.
- After approval, write `.higpertext/roadmap.json` with phases and required skills.
- Each phase in `roadmap.json` must declare: `id`, `name`, `description`, `status` (`pending|active|done`), and `skills`.

# Do not

- Plan cross-file or structural changes without checking the Redis-backed semantic graph or explicitly reporting it unavailable.
- Treat a stale session tool list as proof that a capability is not enabled in the persisted profile.
- Modify files without an approved plan.
- Assume missing modules exist.
- Write `roadmap.json` before the user explicitly approves the plan.
