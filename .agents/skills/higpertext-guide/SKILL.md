---
name: higpertext-guide
description: Higpertext assistant skill.
---

# Higpertext Guide: MCP

- `.higpertext/` es estado compilado: nunca se edita a mano.
- Invoca capabilities mediante MCP y usa `ok`, `summary`, `data`, `artifacts`, `warnings` y `error` como contrato.
- Descubre con `mcp__higpertext__common_list-rules()` y carga detalle con `mcp__higpertext__common_load-rules(rules="<id>")`.
- No reconstruyas una capability como comando ni interpretes logs como contrato.
