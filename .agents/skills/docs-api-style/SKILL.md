---
name: docs-api-style
description: Convención para escribir/actualizar la documentación de contrato en docs/api/*.md de higpertext-server-profile (ejemplos JSON por RPC, errores esperados, valores válidos).
---

# When to use

- Al agregar un RPC nuevo o cambiar el contrato de uno existente en `proto/profile/v1/profile.proto`.
- Al crear o actualizar `docs/api/<servicio>.md`.

# Do

- Encabezado `# <ServiceName>` seguido de un párrafo que arranca citando `profile.v1.<X>Service` — qué es, en qué se diferencia de servicios relacionados (ej. Activity vs LearningEvent vs AuditEvent), e invariantes clave del servicio.
- Una sección `## <NombreDelRPC>` por método, con prosa breve sobre campos requeridos, defaults y validaciones **antes** del ejemplo (no después).
- Bajo cada método, un bloque fenced ```json``` etiquetado **Message:** (o **Message (<contexto>):** si hace falta más de un ejemplo con distinto propósito) con el JSON de request real — debe poder pegarse tal cual en `grpcurl -plaintext -d '<json>' localhost:50051 profile.v1.<Servicio>/<Método>` o en el tab Message de Postman.
- Lista **Errores esperados:** con los codes gRPC (`INVALID_ARGUMENT`, `NOT_FOUND`, `ALREADY_EXISTS`, etc.) y cuándo ocurre cada uno, cuando aplique.
- Separar cada método con `---`.
- Cerrar el doc con `## Valores válidos` listando los dominios de enums o campos de texto libre con vocabulario cerrado (`event`, `decision`, `severity`, `matcher`, etc.) usados por ese servicio.
- Marcar explícitamente cuando un campo es una referencia blanda sin FK (ej. `capability_id`, `project_id`) — el server no la valida contra la tabla relacionada.
- Agregar la entrada nueva al índice de `docs/api/README.md` y, si el mensaje espeja algo de higpertext-cli, sumarla a la tabla de correspondencia; si no, marcarla "Nuevo".

# Do not

- No inventar ejemplos: cada JSON debe ser ejecutable contra el server real, no un placeholder simplificado.
- No mezclar documentación de contrato (este directorio) con decisiones de arquitectura de alto nivel — eso va en `docs/architecture.md`.
- No omitir `## Valores válidos` si el mensaje tiene algún enum o dominio cerrado.
