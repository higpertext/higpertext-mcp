# Tools

Ejemplos de `arguments` por capability, extraídos de sus definiciones reales
en `higpertext-cli` (`src/higpertext/capabilities/**/*.json`). Todas las
capabilities implementan sus parámetros como string (formato CLI), pero eso no
significa que en MCP siempre mandes strings: `schema.py` infiere
`boolean`/`integer`/`string` a partir del `default` declarado en el JSON de la
capability, y el SDK de MCP **valida `arguments` contra ese JSON Schema antes
de ejecutar** — si un parámetro quedó tipado `integer`/`boolean`, mandarlo
entre comillas (`"2"` en vez de `2`) hace fallar la validación.

> Fijate el `type` de cada propiedad en el `inputSchema` que trae `tools/list`
> antes de armar el `arguments` — es más confiable que asumirlo por el nombre.
> En los ejemplos de abajo, cada bloque JSON ya usa el tipo real.

Cada tool solo aparece si (a) el motor la trae instalada y (b) el perfil
activo del proyecto la lista en `capabilities` — ver
[README.md](./README.md#qué-tools-ves-realmente).

> El nombre que ves en `tools/list` **no** es el `capability_id` tal cual
> (`common.grep-search`): el `.` se reemplaza por `-` (`common-grep-search`)
> porque varios clientes MCP (VS Code entre ellos) validan `Tool.name` contra
> `^[a-z0-9_-]+$` y descartan silenciosamente cualquier tool con puntos. Cada
> título de abajo muestra ambos: el nombre de tool real y su `capability_id`.

Respuesta de referencia para todos los ejemplos: ver el contrato
`{ok, summary, data, artifacts, warnings, error}` en [README.md](./README.md#contrato-de-resultado-de-una-tool).

## Herramientas administrativas

Flujo de boards y roadmap para el frontend:

```json
{ "action": "overview", "board_name": "Roadmap" }
```

Acciones disponibles: `list_boards`, `overview`, `migrate`, `create`, `update`,
`move`, `delete`, `delete_board`, `task_create`, `task_update` y `task_delete`.
Para mover una actividad se usa `target` (`Pending`, `Active` o `Done`). La
migración de fases existentes es repetible: identifica cada fase por el tag
`roadmap:<phase_id>` y no duplica tarjetas ya importadas.

Vista operativa para el menú (proyecto, perfil, skills, hooks, capabilities y
manifiestos de render):

```json
{
  "render_limit": 10
}
```

En un gateway multi-proyecto se puede seleccionar el proyecto con
`project_id` o `root_path`; en stdio se usa `HIGPERTEXT_PROJECT_ROOT`.
Después de materializar configuración, `higpertext-render-adapters` devuelve
un `render_id` y deja el manifiesto en
`.higpertext/state/renders/rnd_<id>.json` para consultar historial y detectar
drift.

Vista unificada de un perfil para un menú de administración:

```json
{
  "action": "view",
  "id": "developer"
}
```

La respuesta incluye `profile`, `skills`, `hooks`, `global_hooks` y
`capabilities`. Los hooks globales también se pueden consultar desde el catálogo
independiente con:

```json
{ "action": "list_global" }
```

Para trabajar con una capability como script editable:

```json
{ "action": "source", "id": "custom.echo", "include_files": true }
```

Validar el source Python:

```json
{ "action": "validate", "id": "custom.echo" }
```

Probar o ejecutar una capability autorizada:

```json
{
  "action": "test",
  "id": "custom.echo",
  "arguments": { "value": "hola" }
}
```

`test` y `run` usan el runner MCP actual y requieren que la capability esté
habilitada por el perfil activo. La ejecución aislada en worker (sin acceso de
red y con límites de recursos) queda como siguiente fase del profile server.

El catálogo actual todavía no expone `UpdateCapability`; para editar y guardar
una capability existente hace falta sincronizar ese nuevo RPC con
`higpertext-server-profile`.

---

## `common-grep-search` (capability_id: `common.grep-search`)

Búsqueda de patrón/regex en el código del proyecto, con filtros y salida agrupada.

**Solo lectura** (`readOnlyHint: true`).

```json
{
  "pattern": "TODO",
  "path": "src",
  "include": "*.py",
  "regex": false,
  "case_sensitive": false,
  "context": 2
}
```

---

## `git-diff` (capability_id: `git.diff`)

Cambios locales en el repo git (staged/unstaged/untracked), resumen o diff detallado.

**Solo lectura.**

```json
{ "detail": "true", "files": "src/higpertext_mcp/server.py" }
```

Sin parámetros también es válido (`{}`) — lista archivos modificados sin diff.
`"Working tree limpio"` es una respuesta exitosa, no una falla.

---

## `git-ls-files` (capability_id: `git.ls-files`)

Lista/inspecciona archivos trackeados por git — alternativa segura a `ls`/`find`.

**Solo lectura.**

```json
{
  "path": "src/higpertext_mcp",
  "preset": "python",
  "mode": "tree",
  "max_depth": 2
}
```

`preset`: `all` | `code` | `python` | `web` | `docs` | `config` | `tests`.
`mode`: `list` | `tree` | `summary` | `dirs` | `json`.

---

## `common-smart-read` (capability_id: `common.smart-read`)

Lectura de archivos segura para LLM: en modo `auto` evita volcar archivos
grandes completos y devuelve skeleton/rango/símbolo/resumen según haga falta.

**Solo lectura.**

```json
{ "path": "src/higpertext_mcp/dispatch.py", "mode": "auto" }
```

Leer un símbolo puntual:

```json
{ "path": "src/higpertext_mcp/dispatch.py", "mode": "symbol", "symbol": "call_capability" }
```

Leer un rango de líneas:

```json
{ "path": "src/higpertext_mcp/dispatch.py", "mode": "range", "offset": 40, "limit": 30 }
```

---

## `common-code-skeletonizer` (capability_id: `common.code-skeletonizer`)

Extrae firmas de clases/funciones, docstrings e imports de un archivo,
reemplazando la implementación por `...` — ahorra tokens de contexto.

**Solo lectura.**

```json
{ "path": "src/higpertext_mcp/dispatch.py" }
```

Con `output`, guarda el esqueleto en disco en vez de solo devolverlo en `data`:

```json
{ "path": "src/higpertext_mcp/dispatch.py", "output": ".higpertext/tmp/dispatch.skeleton.py" }
```

---

## `common-memory-manager` (capability_id: `common.memory-manager`)

Persiste un aprendizaje/estado en `.memory/` del proyecto activo. **No es de
solo lectura** — escribe en disco.

```json
{
  "action": "Documentar API de higpertext-mcp",
  "status": "success",
  "notes": "Generados docs/api/tools.md e installation.md.",
  "learned": "El server ya no fija 10 capabilities; depende del perfil activo."
}
```

`status` acepta únicamente `"success"` o `"failure"`; si es `"failure"`,
completá también `failure_root_cause`.

---

## `git-committer` (capability_id: `git.committer`)

Commit siguiendo Conventional Commits, con push/tag opcionales a la rama
indicada. **Side-effect destructivo** — pide confirmación explícita del
usuario antes de invocarla desde un agente (ver Roadmap en el README raíz).

```json
{
  "message": "docs: agrega catálogo de tools MCP",
  "files": "docs/",
  "rationale": "Documentar el contrato real de tools para poder probarlas desde Postman."
}
```

Con tag y bump de versión automático:

```json
{ "message": "feat: nueva capability", "tag": "true", "bump": "minor" }
```

---

## `security-secret-scanner` (capability_id: `security.secret-scanner`)

Escanea código e historial en busca de claves/API keys/tokens/contraseñas
expuestas; genera un reporte Markdown con los hallazgos enmascarados.

**Solo lectura** (el reporte que escribe es el artefacto esperado, no un
side-effect sobre código fuente).

```json
{ "target_path": ".", "output_report": "secret_scan_report.md" }
```

Un reporte sin hallazgos es un resultado válido y esperado, no un indicio de
que la tool falló.

---

## `common-quality-resolver` (capability_id: `common.quality-resolver`)

Actualiza el checklist de remediación (`remediation_todo.md`) a partir de un
reporte de calidad existente. **Destructivo** (`destructiveHint: true`) —
puede reescribir archivos existentes.

```json
{ "report": "code_quality_report.md", "todo_file": "remediation_todo.md", "mode": "update" }
```

Falla con `[ERROR]` (→ `ok: false`) si `report` no existe todavía.

---

## Nota: `common.knowledge-asker`

El `README.md` raíz y `annotations.py` todavía listan `common.knowledge-asker`
como una de las 10 capabilities de v1, pero no existe ninguna definición JSON
con ese `id` en el checkout actual de `higpertext-cli` — `schema.load_tool_spec`
devuelve `None` para ella y el server la omite en silencio (fail-closed, según
diseño). Si tu perfil la lista en `capabilities`, no vas a ver esa tool hasta
que exista la capability real en el motor.
