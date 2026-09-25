# Documentación de API — higpertext-mcp

Este servidor no expone un API HTTP/gRPC: habla el protocolo **MCP** (JSON-RPC
2.0) sobre **stdio**. No hay puerto que golpear con `curl`; el cliente (Claude
Code, Postman, etc.) lanza el proceso y conversa por stdin/stdout.

- [tools.md](./tools.md) — cada tool expuesta, con ejemplo de `arguments` listo
  para pegar en el panel de una tool en Postman (o en el `params.arguments` de
  un `tools/call` JSON-RPC crudo).
- [resources.md](./resources.md) — el único resource expuesto (telemetría de uso).
- [../installation.md](../installation.md) — instalación, configuración en
  `.mcp.json` y cómo probarlo desde Postman.

## Administración de perfiles y catálogo

`higpertext-profile` con `{"action":"view","id":"<perfil>"}` devuelve una
vista agregada para el menú: el perfil, sus skills visibles, sus hooks efectivos,
los hooks globales y sus capabilities autorizadas. Así el menú no necesita
consultar cinco catálogos ni reconstruir scopes.

`higpertext-hook-admin` mantiene el catálogo global separado. Usá
`{"action":"list_global"}` para consultar únicamente hooks con `profiles=[]`.

`higpertext-capability` permite `create`, `source`, `validate`, `test` y `run`.
`test`/`run` sólo aceptan capabilities habilitadas por el perfil activo del
proyecto; una capability existente en el catálogo pero no autorizada no se puede
ejecutar desde esta superficie administrativa.

La edición persistente de un hook o de una capability existente requiere los
RPC `UpdateHook`/`UpdateCapability` en `higpertext-server-profile`; el contrato
actual sólo ofrece crear, consultar y borrar. Esta entrega no borra y recrea
objetos automáticamente para simular una edición.

`higpertext-system-overview` concentra la información que necesita el menú de
operación: proyecto seleccionado, `active_profile`, bundle del perfil (skills,
hooks efectivos, hooks globales y capabilities autorizadas) y los últimos
renderizados. Acepta `project_id` o `root_path` en gateways multi-proyecto; en
stdio usa `HIGPERTEXT_PROJECT_ROOT`. Los renderizados se registran en
`.higpertext/state/renders/rnd_<id>.json` con rutas, resultado, estado y hashes
SHA-256 de los archivos generados, sin copiar su contenido.

`higpertext-roadmap-board` es el contrato único del frontend para el flujo de
trabajo. `overview` devuelve board, columnas, actividades y tasks; `create`,
`update`, `move` y `delete` gestionan tarjetas; `task_create`, `task_update` y
`task_delete` gestionan el checklist; `list_boards` descubre los boards del
proyecto y `migrate` importa `.higpertext/roadmap.json` de forma idempotente
usando tags `roadmap:<phase_id>`. El board persistente vive en
`higpertext-server-profile`; el JSON local se conserva como fuente de migración
y respaldo legible.

## Contrato de resultado de una tool

Los clientes MCP (Claude Code entre ellos) le muestran al modelo el
`structuredContent` serializado cuando existe, no solo el `content` de texto.
Por eso el resultado de una capability tiene tres formas, según lo que emita:

**Texto legado** (stdout que no es JSON): el texto va plano en `content`, **sin**
`structuredContent`. Evita escapar `\n`/`\"` y repetir la primera línea como
`summary`. Los `warnings`, si hay, se agregan al final del texto.

**Datos estructurados** (stdout JSON): `content` = `summary`, y
`structuredContent` con el sobre, **sin campos vacíos** (`artifacts: []`,
`warnings: []`, `error: null` se omiten):

```json
{"ok": true, "summary": "Resultado breve para el agente", "data": {"matches": ["src/a.py:1"]}}
```

**Error**: `isError: true`; `content` y `summary` llevan el diagnóstico (hasta
600 caracteres), no solo su primera línea — el agente necesita la causa para
no reintentar a ciegas. `structuredContent` = `{"ok": false, "summary", "error"}`.

- `ok`: `false` si la capability falló (`returncode != 0`) o violó su
  `contract.rules` técnico.
- `summary`: en éxito, primera línea no vacía de la salida (240 caracteres).
- `data`: stdout parseado como JSON si es un objeto; si es una lista,
  `{"items": [...]}`; texto legado, `{"text": "<stdout>"}` (ver arriba).
- `trace_id`: viaja en `_meta`, fuera de la vista del modelo.

Antes de devolverse, la salida de texto pierde los separadores y banners
puramente visuales (`=====`, `╔──`, `[*] …`) y las rutas del contenedor
(`HIGPERTEXT_PROJECTS_MOUNT`) se reescriben a rutas del host. En la entrada, un
parámetro con ruta absoluta del host se traduce a su ruta montada, y las rutas
relativas se resuelven contra la raíz del proyecto seleccionado.

Ver `src/higpertext_mcp/dispatch.py` y `server.py:capability_call_result`.

## Selección del proyecto en el gateway HTTP

El gateway HTTP es compartido por todos los proyectos del host. Cada cliente
declara su proyecto con el header `X-Higpertext-Project-Root: <ruta host>`,
que `higpertext-render-adapters` / `higpertext-configure-project` escriben en
`.mcp.json` (y en `.agents/mcp_config.json` y `opencode.json`). El gateway lo
traduce a la ruta montada, lo valida contra `HIGPERTEXT_ALLOWED_PROJECT_ROOTS`
y lo usa como raíz del request: perfil activo, tools expuestas y `cwd` de las
capabilities salen de ese proyecto. Una raíz que el contenedor no ve responde
400 (nunca cae a otro proyecto). Sin header se usa `HIGPERTEXT_PROJECT_ROOT`.

## Qué tools ves realmente

**No hay una lista fija de tools.** `list_tools()` se recalcula en cada
llamada como la intersección entre:

1. todas las capabilities que trae instalado el motor `higpertext-cli`, y
2. las `capabilities` declaradas por el `active_profile` del proyecto destino
   (`.higpertext/config/environment.json` → `src/config/profiles/<perfil>.json`).

Sin perfil activo legible, no se expone **ninguna** tool (fail-closed). Si
cambiás de perfil a mitad de sesión, hay que reconectar el cliente MCP — no
hay refresh automático de la lista todavía (el server sí emite
`notifications/tools/list_changed` después de cada `call_tool` si detecta que
el set cambió, pero es el cliente quien decide si vuelve a pedir la lista).

> El README raíz todavía documenta "10 capabilities fijas" — eso describe el
> MVP inicial, no el comportamiento actual. `tools.md` documenta esas mismas
> 9 capabilities (una, `common.knowledge-asker`, ya no existe en el motor
> instalado) a modo de catálogo de referencia, pero cualquier capability que
> tu perfil otorgue también aparece como tool.

## Cómo probar con el JSON-RPC crudo (sin cliente MCP)

Si necesitás depurar a mano, el server lee/escribe JSON-RPC 2.0 enmarcado por
línea (`Content-Length` header, como LSP) por stdin/stdout — así es como lo
harías con `nc`/un script, sin Postman:

```jsonc
// 1. initialize
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual","version":"0"}}}
// 2. notifications/initialized
{"jsonrpc":"2.0","method":"notifications/initialized"}
// 3. listar tools
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
// 4. invocar una
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"git.diff","arguments":{"detail":"false"}}}
```

En la práctica, dejá que Postman (transporte STDIO de una colección MCP) o
Claude Code hagan este handshake por vos — ver [installation.md](../installation.md).
