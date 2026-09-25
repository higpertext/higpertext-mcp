# Resources

## `higpertext://session/usage`

Telemetría real de contexto del proyecto, escrita en Redis por los hooks
`hook_post_observer` (un evento `tool_call` por tool, con `context_tokens`: lo
que el modelo realmente recibió) y `hook_context_usage` (un evento
`context_usage` por turno, leído del `usage` del transcript). Key:
`higpertext:telemetry:<project_id|sha256(raíz host)[:16]>:<sesión>`, TTL 7 días.
Es de solo lectura — no gasta un tool call.

**Leerlo (JSON-RPC):**

```json
{"jsonrpc":"2.0","id":4,"method":"resources/read","params":{"uri":"higpertext://session/usage"}}
```

**Forma de la respuesta** (`src/higpertext_mcp/resources.py:aggregate_usage`):

```json
{
  "tool_calls": 212,
  "tool_context_tokens": 98400,
  "by_tool": {
    "Bash": {"calls": 120, "context_tokens": 44100, "max": 2900, "share_pct": 44.8},
    "Read": {"calls": 40, "context_tokens": 31000, "max": 6100, "share_pct": 31.5}
  },
  "top_outputs": [{"tool": "Read", "context_tokens": 6100, "ts": "2026-09-25T10:02:11+00:00"}],
  "recent_sessions": [
    {"session_id": "…", "tool_calls": 80, "peak_context": 151000, "last_context": 62000, "last_ts": "…"}
  ]
}
```

`by_tool` trae las 15 tools que más contexto consumen; `top_outputs`, las 5
salidas más grandes; `recent_sessions`, las 5 últimas sesiones con su pico de
contexto. Los eventos anteriores a `context_tokens` usan `output_tokens`,
salvo Edit/Write (cuyo payload trae el archivo entero, que no entra al
contexto: se cuentan como acuse de ~20 tokens). Sin Redis o sin datos, todos
los contadores en cero y listas vacías.

### `context_misses`: ¿los recortes dejan al agente sin contexto?

Toda salida recortada (Bash resumido, `smart-read` por rango/skeleton,
`grep-search` con límites) declara lo omitido con el marcador estándar
`[htx:omitted <qué>; <cómo pedirlo>]`. `hook_post_observer` anota por tool call
`truncated`, `fingerprint` (qué se pidió, sin parámetros de tamaño) y
`saved_output_lookup` (abrió el output completo guardado). El resource cruza esos
eventos:

```json
"context_misses": {
  "truncated_outputs": 12,
  "refetched_after_truncation": 1,
  "saved_output_lookups": 2,
  "miss_rate_pct": 8.3,
  "by_tool": {"Bash": {"truncated": 4, "refetched": 1}},
  "repeat_calls": {"Read": 6}
}
```

- **miss**: un recorte seguido, dentro de las 8 tool calls siguientes, de la
  misma llamada (misma `fingerprint`): el agente tuvo que volver a buscar.
- `saved_output_lookups`: recuperaciones baratas vía el archivo guardado; no
  cuentan como miss.
- `repeat_calls`: la misma llamada repetida sin recorte previo, típico tras
  perder contexto por compactación.

Para evaluar un cambio de umbral **antes** de desplegarlo, `scripts/context_miss_replay.py`
reproduce el filtro vigente sobre los transcripts reales y reporta recortes,
misses y ahorro por umbral.
