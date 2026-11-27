# Documentos de referencia de IOL

Snapshots de la documentacion oficial de IOL, guardados aca para que el contrato
que implementa la libreria sea auditable sin depender de la red.

| Archivo | Origen | Que cubre |
|---|---|---|
| `iol-api-v1.md` | `https://developers.iolinversiones.com/api/llms` | Los 35 endpoints REST con sus esquemas, tal como los publica IOL (OpenAPI 3.1.2, API v1.0.0) |
| `iol-websocket-guia-ia.md` | Descarga "guia para IA" de la seccion WebSocket de IOL (version del documento: 2026-11-06) | Conexion, autenticacion, suscripcion, heartbeat, canales `quotes`/`order_book`/`trades`, limites y codigos de error |

## Licencia

Estos archivos **no** estan cubiertos por la licencia MIT de este repositorio: son
documentacion de IOL Inversiones y los derechos son de IOL. Se incluyen como
referencia tecnica para implementar un cliente interoperable, sin animo de
redistribucion comercial.

Si IOL pide que se retiren, se retiran: la libreria no depende de ellos para
funcionar, solo para auditar el contrato.

## Como refrescarlos

```bash
# REST: el endpoint que sirve el contrato renderizado
curl -s https://developers.iolinversiones.com/api/llms -o doc/vendor/iol-api-v1.md

# WebSocket: la guia para IA se descarga desde la seccion de documentacion
# (https://developers.iolinversiones.com/docs/websocket). El endpoint HTML
# tambien sirve para reconstruirla a mano si cambia el formato de descarga.
curl -s https://developers.iolinversiones.com/docs/websocket -o /tmp/ws.html
```

Despues de refrescar, comparar antes de commitear:

```bash
git diff --stat doc/vendor/          # tamano del cambio
git diff doc/vendor/iol-api-v1.md | head -80
```

Si el diff toca esquemas, seguir [`../maintenance-guide.md`](../maintenance-guide.md):
ahi esta el paso a paso de que tocar en el codigo y como verificarlo.

## Fecha del ultimo sync

- `iol-api-v1.md`: 2026-11-21 (API v1.0.0, OpenAPI 3.1.2)
- `iol-websocket-guia-ia.md`: version del documento 2026-11-06
