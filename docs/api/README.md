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

## Contrato de resultado de una tool

Toda tool (sin importar la capability que envuelva) devuelve
`structuredContent` con esta forma fija — es el contrato real, no una
transcripción de terminal:

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

- `ok`: `false` si la capability falló (`returncode != 0`) o violó su
  `contract.rules` técnico.
- `summary`: primera línea no vacía de la salida de la capability, recortada a
  240 caracteres. Es lo único que aparece en el `content` de texto del tool.
- `data`: `stdout` de la capability parseado como JSON si es un objeto; si es
  una lista, se envuelve como `{"items": [...]}`; si no es JSON válido (texto
  plano legado), se envuelve como `{"text": "<stdout>"}`.
- `warnings`: normalizaciones no destructivas que aplicó la validación de
  parámetros (ej. un alias resuelto a su nombre canónico).
- `error`: solo presente si `ok = false` — mensaje de contrato o el
  stderr/stdout combinado de la capability.

Ver `src/higpertext_mcp/dispatch.py` para la implementación exacta.

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
