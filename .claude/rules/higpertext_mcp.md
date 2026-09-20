# higpertext_mcp

Perfil del proyecto higpertext-mcp: servidor MCP (Python) que expone capabilities/hooks del profile server como tools reales (function-calling) — el punto de entrada que usan los asistentes (Claude Code, etc.) hacia todo el ecosistema higpertext.

Trabajás en higpertext-mcp: el servidor MCP en Python que expone las capabilities del profile server como tools MCP genuinas (function-calling con schema validado), reemplazando el viejo interceptor de texto sobre Bash de higpertext-cli.

Reglas de arquitectura de este repo:
- Contrato de resultado uniforme para toda tool: `{ok, summary, data, artifacts, warnings, error}` — el mensaje visible al agente es solo `summary`; texto libre legado va en `data.text`, nunca reemplaza `summary`.
- Qué capabilities se exponen no es un set fijo en código: se registra como tool toda capability que esté en el catálogo del profile server Y listada en el `active_profile` del proyecto destino (`.higpertext/config/environment.json`). Sin perfil activo o ilegible, no se expone ninguna tool — fail-closed, nunca degradar a "exponer todo por las dudas".
- La resolución de la raíz del proyecto destino (`discovery.py:resolve_project_root`) requiere `HIGPERTEXT_PROJECT_ROOT` o un selector explícito de la operación — deliberadamente NO usa la raíz del motor instalado (`higpertext.kernel.config_paths.PROJECT_ROOT`).
- `profile_client.py` habla gRPC puro contra el profile server (`ProjectService`, `SkillService`, `HookService`, etc.) — es el único punto de este repo que debe tocar la red hacia el profile server; no duplicar llamadas gRPC sueltas en otros módulos.
- Cualquier cambio a `proto/profile/v1/profile.proto` en este repo es una copia vendored del `.proto` real de higpertext-server-profile — hay que resincronizarla a mano (`python -m grpc_tools.protoc`) cada vez que el lado Go cambia el contrato; quedan desincronizados si solo se toca uno de los dos lados.

## Capabilities activas

- `common.agent-acceptance` — Evalúa criterios de aceptación de un agente higpertext y genera evidencia JSON para CI.
- `common.code-skeletonizer` — Genera una versión 'esqueleto' de un archivo de código fuente (especialmente Python mediante AST, y otros lenguajes mediante expresiones regulares), extrayendo solo firmas de clases, funciones/métodos, docstrings e imports, omitiendo el código de implementación para ahorrar tokens de contexto.
- `common.context-assembler` — Ensambla un 'context pack' curado para una tarea concreta. Dado un objetivo y tipo, extrae keywords, selecciona del semantic graph solo los símbolos relevantes bajo un presupuesto de tokens, y genera un artefacto Markdown en .higpertext/state/context_packs/. Provee al agente el contexto mínimo-suficiente en vez de explorar el repo a ciegas.
- `common.context-budget-report` — Estima cuánto contexto consume una lectura, búsqueda o skeleton antes de ejecutarla y recomienda read range, skeleton, summary o grep.
- `common.error-context-locator` — Extrae file:line desde trazas, errores o logs y devuelve contexto mínimo con sugerencias de smart-read focalizado.
- `common.governance-exception` — Registra o lista excepciones aprobadas a reglas de gobernanza para un perfil.
- `common.graph-query` — Consulta el grafo semántico (persistido en Redis por common.graph-rebuild, key higpertext:semantic_graph:&lt;sha256(root)[:16]&gt;) para encontrar símbolos relacionados con un nombre o keyword, expandiendo vecinos hasta una profundidad configurable. Cada símbolo devuelto puede alcanzarse por relaciones con distinta confidence (1.0 = inequívoco por sintaxis, menor = requeriría resolver tipos con un compilador) heredada de common.graph-rebuild.
- `common.graph-rebuild` — Regenera el grafo semántico del proyecto y lo persiste ÚNICAMENTE en Redis (higpertext:semantic_graph:&lt;sha256(root)[:16]&gt;). Parsers reales: ast para Python; tree-sitter para C#, F#, Go, C, C++, JavaScript/JSX, TypeScript/TSX y COBOL; regex de mejor esfuerzo para VB.NET (no existe gramática tree-sitter mantenida). Cada relación lleva confidence: 1.0 para lo inequívoco por sintaxis (imports/using/open), menor cuando resolver el destino real requeriría un compilador (herencia ambigua, llamadas calificadas). Java/Kotlin/Ruby/PHP/Swift/Rust/Scala/Perl/Lua se reconocen y se reportan como no soportados explícitamente, nunca se ignoran en silencio.
- `common.grep-search` — Busca un patrón literal o regex en el código/texto del proyecto (y opcionalmente en el grafo semántico). Para un símbolo único ya conocido en un repo mediano, un grep directo suele ser más barato — usa esta capability para búsquedas amplias, con filtros/presets, o cuando quieras salida agrupada y priorizada por relevancia.
- `common.memory-manager` — Persiste aprendizajes y estados después de cada acción del agente.
- `common.quality-resolver` — Actualiza el checklist de remediación a partir de un reporte de calidad.
- `common.search-router` — Recomienda el plan de capacidades adecuado para localizar contexto: error-context-locator, smart-read, graph-query o grep-search según intención y query.
- `common.semantic-search` — Busca fragmentos de código/documentación semánticamente usando el índice RAG persistido en Redis por common.rag-index (key higpertext:vector_store:<sha256(root)[:16]>). Ya no lee .higpertext/state/vector_store.json.
- `common.skill-resolver` — Selecciona, del catálogo de skills FIJAS del motor (templates/skills/), cuáles son relevantes para el objetivo puntual de la tarea actual — una capa temporal encima de session_skills, no un reemplazo. No genera contenido de skill nuevo, solo elige entre las ya existentes por coincidencia de keywords.
- `common.smart-read` — Lee archivos de forma segura para LLM. En modo auto evita volcar archivos grandes y devuelve skeleton, rangos, símbolos o resumen con mapa de líneas.
- `common.subagent-executor` — Lanza la ejecución aislada de un subagente especializado para resolver una subtarea.
- `common.truth-keeper` — Lee, escribe y gestiona el contexto de la Fuente de Verdad en .memory/truth.json para consulta rápida por agentes.
- `security.secret-scanner` — Escanea el código fuente e historial en busca de claves API expuestas, PATs, tokens y contraseñas.
- `security.secret-set` — Guarda, elimina o consulta el estado de la API key de un provider LLM en el llavero nativo del sistema operativo (Keychain / Secret Service / Credential Manager).

## Hooks activos (Claude Code)

- `hook_audit` (PostToolUse, matcher=`*`) — Audit hook: registra en AuditService cada acción que efectivamente se ejecutó (llegar a PostToolUse implica que ningún PreToolUse la bloqueó). Complementa el registro inline que hook_bash_guard/hook_security_guard_pre hacen en el momento de un block/warn.
- `hook_bash_guard` (PreToolUse, matcher=`Bash`) — Evalúa en cadena las reglas de comandos Bash: bloques duros (peso 5, precondition), deployment gate, reglas de perfil con peso 1-5 (policy). Registra cada block/warn en AuditService.
- `hook_read_guard` (PreToolUse, matcher=`Read`) — Bloquea lecturas completas de archivos grandes y recomienda smart-read o code-skeletonizer.
- `hook_security_guard_post` (PostToolUse, matcher=`*`) — Enmascara secretos detectados en outputs de herramientas.
- `hook_security_guard_pre` (PreToolUse, matcher=`Bash|PowerShell|Read|Write|Edit`) — Bloquea comandos y rutas sensibles según reglas de seguridad. Registra cada block/warn en AuditService.

## Gobernanza activa

Estas reglas son de cumplimiento obligatorio en todo el desarrollo:

- [CRITICAL w=5] **sec-pip-venv** — Las instalaciones de paquetes deben hacerse en el entorno controlado .venv. Usa '.venv/bin/pip install <paquete>' o gestiona dependencias desde pyproject.toml. (enforced: `(?<!venv[/\\]bin[/\\])(?<!Scripts[/\\])\bpip\s+install\b|(?<!venv[/\\]bin[/\\])(?<!Scripts[/\\])\bpip3\s+install\b`)

---

*higpertext-mcp — configuración generada por la integración centralizada de adapters. No editar manualmente; modificar el catálogo o el profile server y volver a renderizar.*
