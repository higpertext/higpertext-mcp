# higpertext-mcp

## Eventos canónicos

Los adapters traducen los eventos nativos de cada asistente a un catálogo
independiente de plataforma: `SESSION_STARTED`, `PROMPT_RECEIVED`,
`PLAN_CREATED`, `ACTION_REQUESTED`, `ACTION_AUTHORIZED`, `ACTION_STARTED`,
`ACTION_COMPLETED`, `ACTION_FAILED`, `CONTEXT_COMPACTING` y
`SESSION_FINISHED`.

La traducción se implementa en `higpertext_mcp.events` y
`higpertext_mcp.hook_protocol`. Cada adapter declara qué eventos puede
observar y sus limitaciones. En particular, `ACTION_AUTHORIZED` no lo emite
un hook: la autorización efectiva pertenece al gateway/controller.

## Catálogo central de adaptadores

La matriz de compatibilidad vive en
`src/higpertext_mcp/adapter_catalog.py`. Es la única fuente de verdad para los
destinos nativos, eventos, aliases de tools, skills y agents, y el
estado de cada integración. Los renderizadores consultan ese catálogo y no
deben declarar asistentes o rutas por separado.

Un adaptador puede ser `native` (formato documentado), `bridge` (puente local)
o no tener una feature concreta. Que exista un hook no convierte el evento en
una garantía de seguridad: la autorización efectiva sigue perteneciendo al
gateway/controller.

Servidor MCP que expone capabilities de `higpertext-cli` como tools reales
(function-calling), en vez del interceptor de texto sobre Bash que usaba antes el motor.

> Documentación completa: [docs/installation.md](./docs/installation.md)
> (instalación, `.mcp.json`, cómo probarlo desde Postman) y
> [docs/api/README.md](./docs/api/README.md) (contrato de respuesta y catálogo
> de tools con ejemplos de `arguments`).

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

## Qué capabilities se exponen

No es un set fijo: se registra como tool cualquier capability que (a) el
motor `higpertext-cli` instalado traiga y (b) esté listada en `capabilities`
del perfil activo del proyecto destino (`.higpertext/config/environment.json`
→ `active_profile` → `src/config/profiles/<perfil>.json`). Sin perfil activo o
legible, no se expone ninguna tool (fail-closed).

El catálogo probado hasta ahora (9 capabilities reales, documentadas con
ejemplos en [docs/api/tools.md](./docs/api/tools.md)):
`common.grep-search`, `git.diff`, `git.ls-files`, `common.smart-read`,
`common.code-skeletonizer`, `common.memory-manager`, `git.committer`,
`security.secret-scanner`, `common.quality-resolver`. Un décimo id,
`common.knowledge-asker`, sigue en `annotations.py` pero no tiene definición
JSON en el motor instalado — nunca se expone hasta que exista.

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

El servidor no usa la raíz del motor ni el `cwd` como selección implícita. En
stdio se debe configurar `HIGPERTEXT_PROJECT_ROOT`; en HTTP cada operación debe
enviar `project_id` o `root_path`, que se valida contra el registro de proyectos.
Para limitar adicionalmente el filesystem de una instancia HTTP/Docker, el
operador puede definir `HIGPERTEXT_ALLOWED_PROJECT_ROOTS` con rutas host
canónicas separadas por `:` (o por `os.pathsep` en la plataforma).

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
