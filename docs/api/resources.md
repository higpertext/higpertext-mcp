# Resources

## `higpertext://session/usage`

Telemetría real de tokens/costo acumulada por el motor higpertext
(`.higpertext/state/telemetry.jsonl`, escrita por `hook_post_observer.py`),
agregada por tool. Es de solo lectura — no gasta un tool call, el modelo la
lee pasivamente vía `resources/read`.

**Leerlo (JSON-RPC):**

```json
{"jsonrpc":"2.0","id":4,"method":"resources/read","params":{"uri":"higpertext://session/usage"}}
```

**Forma de la respuesta** (`src/higpertext_mcp/resources.py:summarize_usage`):

```json
{
  "total_tokens": 18420,
  "total_cost_usd": 0.0512,
  "calls": 7,
  "by_tool": {
    "common.grep-search": { "tokens": 6200, "cost_usd": 0.0173, "calls": 3 },
    "git.diff": { "tokens": 1100, "cost_usd": 0.0031, "calls": 2 }
  }
}
```

Si `.higpertext/state/telemetry.jsonl` no existe todavía en el proyecto
destino (sesión nueva, sin tool calls previos), devuelve el objeto vacío por
defecto: `{"total_tokens": 0, "total_cost_usd": 0.0, "calls": 0, "by_tool": {}}`.
