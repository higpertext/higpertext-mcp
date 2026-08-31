# higpertext-mcp

Servidor MCP que expone 10 capabilities de `higpertext-cli` como tools reales
(function-calling), en vez del interceptor de texto sobre Bash que usaba antes el motor.

## Por qué existe

Ver la discusión de diseño en el historial del proyecto `higpertext-cli`
(`bash_rules.py`, `hook_bash_guard.py`): los redirects de texto sobre Bash
(`grep`, `git diff/status`, etc.) interceptaban el comando, ejecutaban la capability
en un subprocess aparte y el comando original corría de todos modos — ruido sin
efecto real. Este servidor reemplaza esa capa con tools MCP genuinas: el modelo
invoca la capability directamente, con schema validado, sin pasar por Bash.

## Contrato de resultados

Cada invocación devuelve `structuredContent`, no una transcripción de terminal:

```json
{
  "ok": true,
  "summary": "Resultado breve para el agente",
  "data": {},
  "artifacts": [],
  "warnings": [],
  "error": null
}
```

Las capabilities que todavía escriben texto se encapsulan temporalmente en
`data.text`; el mensaje visible del tool contiene sólo `summary`. El CLI `htx`
sigue disponible para personas y CI, pero ya no imprime el `stdout` completo de
una capability exitosa.

## Capabilities v1 (10, fijas)

`common.grep-search`, `git.diff`, `git.ls-files`, `common.smart-read`,
`common.code-skeletonizer`, `common.knowledge-asker`, `common.memory-manager`,
`git.committer`, `security.secret-scanner`, `common.quality-resolver`.

Solo se registran como tool las que además estén listadas en `capabilities` del
perfil activo del proyecto destino (`.higpertext/config/environment.json` →
`active_profile` → `src/config/profiles/<perfil>.json`). Sin perfil activo o
legible, no se expone ninguna tool (fail-closed).

## Instalación

`higpertext-cli` es un paquete propietario, no está en PyPI — se instala editable
apuntando al checkout local, igual que `agent-bootstrap` lo hace para agentes
externos:

```bash
python3 -m venv .venv
.venv/bin/pip install -e /ruta/a/higpertext-cli
.venv/bin/pip install -e .
```

## Uso con Claude Code

Agregar en `.mcp.json` del proyecto destino (el que tiene su propio
`.higpertext/`):

```json
{
  "mcpServers": {
    "higpertext": {
      "command": "/ruta/a/higpertext-mcp/.venv/bin/python",
      "args": ["-m", "higpertext_mcp.server"]
    }
  }
}
```

El servidor resuelve la raíz del proyecto por `cwd` del proceso (el cliente MCP
local lo lanza con cwd = raíz del proyecto). Para forzar otra raíz, setear
`HIGPERTEXT_PROJECT_ROOT` en el bloque `env` de la entrada del server en
`.mcp.json`.

**Limitación conocida (v1)**: la lista de tools se arma una sola vez, al conectar.
Si cambiás de perfil (`htx profile load`) a mitad de sesión, hay que reconectar el
server para que la lista de tools se actualice — no hay refresh automático todavía.

## Tests

```bash
.venv/bin/python -m pytest tests -q
```

Dos tests (`test_load_tool_spec_real_grep_search`,
`test_call_capability_real_grep_search_on_this_repo`) son de integración real: usan
la definición real de `common.grep-search` del motor instalado, así que hay que
correrlos con `higpertext-cli` instalado editable (ver Instalación) y cwd dentro de
un checkout de `higpertext-cli` real.

## Roadmap (no construido todavía)

- Resto de las ~37 capabilities restantes del motor.
- Refresh de tools al cambiar de perfil sin reconectar.
- Confirmación explícita antes de invocar capabilities con side-effects
  destructivos (`git.committer`, `common.memory-manager`).
