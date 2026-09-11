# Perfil higpertext: higpertext_mcp

Perfil del proyecto higpertext-mcp: servidor MCP (Python) que expone capabilities/hooks del profile server como tools reales (function-calling) — el punto de entrada que usan los asistentes (Claude Code, etc.) hacia todo el ecosistema higpertext.

## Mandato del perfil

Trabajás en higpertext-mcp: el servidor MCP en Python que expone las capabilities del profile server como tools MCP genuinas (function-calling con schema validado), reemplazando el viejo interceptor de texto sobre Bash de higpertext-cli.

Reglas de arquitectura de este repo:
- Contrato de resultado uniforme para toda tool: `{ok, summary, data, artifacts, warnings, error}` — el mensaje visible al agente es solo `summary`; texto libre legado va en `data.text`, nunca reemplaza `summary`.
- Qué capabilities se exponen no es un set fijo en código: se registra como tool toda capability que esté en el catálogo del profile server Y listada en el `active_profile` del proyecto destino (`.higpertext/config/environment.json`). Sin perfil activo o ilegible, no se expone ninguna tool — fail-closed, nunca degradar a "exponer todo por las dudas".
- La resolución de la raíz del proyecto destino (`discovery.py:resolve_project_root`) usa `HIGPERTEXT_PROJECT_ROOT` o el cwd del proceso servidor — deliberadamente NO usa la raíz del motor instalado (`higpertext.kernel.config_paths.PROJECT_ROOT`), que resolvería el lugar equivocado.
- `profile_client.py` habla gRPC puro contra el profile server (`ProjectService`, `SkillService`, `HookService`, etc.) — es el único punto de este repo que debe tocar la red hacia el profile server; no duplicar llamadas gRPC sueltas en otros módulos.
- Cualquier cambio a `proto/profile/v1/profile.proto` en este repo es una copia vendored del `.proto` real de higpertext-server-profile — hay que resincronizarla a mano (`python -m grpc_tools.protoc`) cada vez que el lado Go cambia el contrato; quedan desincronizados si solo se toca uno de los dos lados.

## Gobernanza efectiva

- Sin active_profile legible en .higpertext/config/environment.json del proyecto destino, no se expone ninguna tool MCP — fail-closed, nunca listar el catálogo completo como fallback.
- resolve_project_root() usa HIGPERTEXT_PROJECT_ROOT/cwd del proceso servidor, nunca la raíz del motor instalado — confundir ambas raíces rompe la resolución de perfil/capabilities del proyecto destino real.
- proto/profile/v1/profile.proto en este repo es una copia vendored: todo cambio al .proto real de higpertext-server-profile debe resincronizarse acá con python -m grpc_tools.protoc antes de usar los campos/RPCs nuevos desde Python (ver custom.proto-dual-stub-check en higpertext-server-profile).
- Las instalaciones de paquetes deben hacerse en el entorno controlado del proyecto (editable install de higpertext-cli / venv), nunca en el Python del sistema.
- [CRITICAL] **sec-pip-venv** — Las instalaciones de paquetes deben hacerse en el entorno controlado .venv. Usa '.venv/bin/pip install <paquete>' o gestiona dependencias desde pyproject.toml.

## Descubrimiento y permisos

- El servidor MCP es la fuente de verdad de capabilities disponibles y permisos efectivos.
- Antes de elegir una capability, consulta las tools MCP disponibles en esta sesión.
- Invoca sólo tools expuestas por el MCP; no infieras capabilities desde este archivo.
- El servidor aplica el perfil activo y rechaza operaciones no autorizadas.
