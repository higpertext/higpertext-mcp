---
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
