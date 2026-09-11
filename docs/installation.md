# Instalación y configuración

`higpertext-mcp` es un servidor **MCP sobre stdio** (`mcp.server.stdio`, sin
HTTP/SSE): un cliente MCP lo lanza como subproceso y le habla por
stdin/stdout, no hay puerto ni URL involucrados.

> Si usás el `deploy/docker-compose.yml` de `higpertext-server-profile`, se
> publica además el transporte Streamable HTTP en
> `http://127.0.0.1:8790/mcp/`. Ese despliegue incluye Redis, profile server,
> importación de capabilities y perfil inicial automático; es la vía
> recomendada para evitar configurar un venv o stdio en cada cliente.

## 1. Requisitos

- Python ≥ 3.10.
- Un checkout local de `higpertext-cli` — es un paquete propietario, no está
  en PyPI, así que se instala en modo editable apuntando a la ruta local.
- Un proyecto destino con `.higpertext/` inicializado y un **perfil activo**
  (`.higpertext/config/environment.json` → `active_profile`) que declare al
  menos una capability en `capabilities` — sin eso el server no expone
  ninguna tool (fail-closed, ver [docs/api/README.md](./api/README.md#qué-tools-ves-realmente)).

## 2. Instalar

```bash
cd /ruta/a/higpertext-mcp
python3 -m venv .venv
.venv/bin/pip install -e /ruta/a/higpertext-cli
.venv/bin/pip install -e .
```

Verificar que quedó instalado:

```bash
.venv/bin/python -c "import higpertext_mcp; print('ok')"
```

## 3. Configurar el cliente MCP

Al conectarse por primera vez, la tool `higpertext-configure-project` está
siempre disponible incluso si todavía no hay perfil activo. Invocala con el
nombre de un perfil que ya exista en `higpertext-server-profile`, por ejemplo:

```json
{ "profile": "agent_designer" }
```

Genera `.higpertext/config/environment.json`,
`.higpertext/config/mcp_external.json` y una entrada `higpertext` en
`.mcp.json`. Conserva los campos y servidores ya existentes y nunca los
sobrescribe. Reconectá el cliente MCP al terminar para que lea el perfil y
publique sus capabilities.

En el despliegue HTTP, las tools `higpertext-configure-project` y
`higpertext-render-adapters` aceptan `project_id` o `root_path` para elegir
explícitamente cualquiera de las rutas físicas registradas. Todas las rutas
siguen compartiendo el mismo `project_id`, pero cada checkout conserva su
propio `.higpertext` y sus propios archivos `.claude`, `.codex`, etc. Nunca se
generan archivos en el directorio del servidor MCP.

En el transporte STDIO, el server resuelve la raíz del proyecto por el
**cwd del proceso** en el que se lanza (no por el cwd de `higpertext-mcp`).
También se puede fijar explícitamente con:

- dejar que el cliente MCP lo lance con `cwd` = raíz del proyecto destino
  (patrón estándar en Claude Code: el `.mcp.json` vive en la raíz del
  proyecto destino, y el cliente lanza el proceso ahí), o
- forzarla explícitamente con la variable de entorno `HIGPERTEXT_PROJECT_ROOT`.

En Docker, el despliegue HTTP monta el conjunto de proyectos en `/projects`.
`HIGPERTEXT_PROJECTS_ROOT` permite cambiar la raíz host que se monta; por
defecto usa `/home/aomerge/Documentos/Proyects`. El MCP traduce las rutas host
recibidas por las tools a esa ruta estable dentro del contenedor.

> **No uses `~` en `command`.** Postman y Claude Code lanzan el proceso con
> `spawn()` directo (sin pasar por una shell), que no expande `~` a tu home —
> el intento de ejecutar la ruta literal falla con `EACCES`/`ENOENT`. Escribí
> siempre la ruta absoluta expandida (`/home/tu-usuario/...`, no `~/...`).

### Claude Code

En `.mcp.json` **del proyecto destino** (no en el repo de `higpertext-mcp`):

```json
{
  "mcpServers": {
    "higpertext": {
      "command": "/home/aomerge/Documentos/Proyects/higpertext-mcp/.venv/bin/python",
      "args": ["-m", "higpertext_mcp.server"]
    }
  }
}
```

Para forzar la raíz sin depender del cwd con el que Claude Code lance el
proceso (usá la raíz del **proyecto destino**, no la de `higpertext-mcp`):

```json
{
  "mcpServers": {
    "higpertext": {
      "command": "/home/aomerge/Documentos/Proyects/higpertext-mcp/.venv/bin/python",
      "args": ["-m", "higpertext_mcp.server"],
      "env": { "HIGPERTEXT_PROJECT_ROOT": "/home/aomerge/Documentos/Proyects/<proyecto-destino>" }
    }
  }
}
```

### Postman

Postman soporta un tipo de colección **MCP** con transporte STDIO — no hace
falta exponer nada por HTTP:

1. `New` → colección **MCP** → **Transport type: STDIO**.
2. **Command**: `/ruta/a/higpertext-mcp/.venv/bin/python`
3. **Arguments**: `-m higpertext_mcp.server`
4. **Working directory**: la raíz del proyecto destino (o, si Postman no
   expone ese campo en tu versión, seteá `HIGPERTEXT_PROJECT_ROOT` como
   variable de entorno de la colección).
5. Conectar — Postman hace el handshake `initialize` y lista Tools/Resources
   automáticamente.
6. Para el detalle de qué mandar en cada tool, ver
   [docs/api/tools.md](./api/tools.md).

Detalles del contrato de respuesta y ejemplos de `arguments` por capability:
[docs/api/README.md](./api/README.md) y [docs/api/tools.md](./api/tools.md).

> **¿Postman instalado vía Flatpak?** El comando de arriba puede fallar con
> `Connection closed` casi instantáneo, incluso con la ruta absoluta bien
> escrita. No es un bug de este server — es un problema de sandbox. Ver la
> sección dedicada: [Postman vía Flatpak](#postman-instalado-vía-flatpak-connection-closed).

## Postman instalado vía Flatpak: `Connection closed`

Si Postman es la versión de **Flatpak** (`flatpak list | grep -i postman` para
confirmarlo), conectar a este server puede fallar con
`Couldn't run the request: Connection closed` casi al instante (milisegundos
después de "Connecting..."), sin importar que el `command` tenga la ruta
absoluta correcta y el binario tenga permiso de ejecución.

**Causa real** (no es un bug de `higpertext-mcp`, ni de tu config): un venv de
Python normal (`python3 -m venv`) crea `.venv/bin/python` como una cadena de
symlinks que termina en un symlink **absoluto** hacia el intérprete del
sistema, ej. `.venv/bin/python3 -> /usr/bin/python3.14`. Fuera de un sandbox
eso resuelve a tu Python real. Pero un proceso lanzado *dentro* del sandbox de
Flatpak de Postman tiene su propio `/usr` — el del runtime de Flatpak
(`org.freedesktop.Platform`), no el de tu sistema. Esa ruta absoluta termina
resolviendo al Python **del runtime** (con otra versión, sin
`higpertext_mcp` instalado), que revienta en milisegundos con
`ModuleNotFoundError` — de ahí el cierre casi instantáneo de la conexión.
Ampliar los permisos de filesystem del Flatpak (`--filesystem=host`) **no
alcanza** para arreglar esto, porque el problema no es de visibilidad de
archivos sino de qué `/usr` ve el symlink al resolverse.

### Fix: usar `flatpak-spawn --host`

`flatpak-spawn --host` le pide al Flatpak system helper que ejecute el
comando directamente en tu sistema, sin pasar por el `/usr` del sandbox — el
symlink del venv resuelve correctamente porque ya no está *dentro* del
sandbox al resolverse.

1. Habilitar el permiso que lo permite (una sola vez, no requiere sudo):

   ```bash
   flatpak override --user --talk-name=org.freedesktop.Flatpak com.getpostman.Postman
   ```

   Cerrá Postman completamente (todas las ventanas, verificá con
   `flatpak ps | grep -i postman` que no quede ningún proceso vivo) y volvé a
   abrirlo — el override solo aplica a instancias nuevas del sandbox.

2. En la colección MCP de Postman, cambiá **Command** y **Arguments** para
   pasar por `flatpak-spawn` en vez de invocar el python del venv directo:

   - **Command**: `/usr/bin/flatpak-spawn`
   - **Arguments** (todo junto, separado por espacios):
     ```
     --host --directory=/ruta/al/proyecto-destino --env=HIGPERTEXT_PROJECT_ROOT=/ruta/al/proyecto-destino /ruta/a/higpertext-mcp/.venv/bin/python -m higpertext_mcp.server
     ```
     `--directory` fija el cwd en el proceso host (equivalente al `cwd`/`HIGPERTEXT_PROJECT_ROOT` de siempre) y `--env` pasa la variable de entorno explícitamente — `flatpak-spawn --host` no hereda el entorno del sandbox por defecto, así que no alcanza con la pestaña "Environment" de Postman para esto.

3. Conectar de nuevo.

Verificación rápida desde una terminal normal (sin pasar por la UI de
Postman), para confirmar que el override + `flatpak-spawn` funcionan antes de
tocar la config:

```bash
flatpak run --command=flatpak-spawn com.getpostman.Postman \
  --host /ruta/a/higpertext-mcp/.venv/bin/python -c \
  "import higpertext_mcp; print('ok', higpertext_mcp.__file__)"
```

Si eso imprime `ok /ruta/.../higpertext_mcp/__init__.py`, el problema está
resuelto y solo falta actualizar el comando en Postman.

## 4. Federar otros servidores MCP (opcional)

`higpertext-mcp` puede fusionar tools de otros servidores MCP externos (solo
transporte stdio, v1) bajo el prefijo `external.<server>.<tool>`. Se declaran
en `.higpertext/config/mcp_external.json`, en el proyecto destino:

```json
{
  "servers": [
    { "name": "otro-server", "command": "/ruta/al/otro/server", "args": [] }
  ]
}
```

Un servidor externo que falla al iniciar o se cae después nunca tumba
`higpertext-mcp` — desaparece de `list_tools()` y loguea a stderr (nunca a
stdout, rompería el protocolo).

## 5. Verificar

```bash
cd /ruta/al/proyecto/destino
/ruta/a/higpertext-mcp/.venv/bin/python -m higpertext_mcp.server
```

Con el proceso corriendo (queda esperando en stdin), reconectá desde tu
cliente MCP y confirmá que la lista de tools no está vacía. Si está vacía:

- revisá que `.higpertext/config/environment.json` tenga `active_profile` seteado, y
- que ese perfil (`src/config/profiles/<perfil>.json`) declare `capabilities` reales.

## 6. Tests (para desarrollo del propio server)

```bash
.venv/bin/python -m pytest tests -q
```

Dos tests son de integración real contra la definición real de
`common.grep-search` — hace falta correrlos con cwd dentro de un checkout de
`higpertext-cli` real (ver Roadmap/limitaciones en el `README.md` raíz).

## Límite conocido

Si cambiás de perfil (`htx profile load`) a mitad de sesión, hay que
**reconectar** el cliente MCP — la lista de tools no se refresca sola todavía.
