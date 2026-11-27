# API WebSocket de IOL Inversiones: guía para asistentes de IA

> Versión del documento: 2026-11-06. Fuente: documentación oficial en https://developers.iolinversiones.com/docs/websocket

## Cómo usar este documento

Este documento está pensado para que lo cargues como contexto en un asistente de IA (ChatGPT, Claude, Copilot, Gemini u otro). Con esto la IA puede entender cómo funciona la conexión WebSocket de IOL y escribir programas de ejemplo que sigan puntas, profundidad y operaciones (último precio y variación) de uno o de muchos activos.

**Instrucciones para la IA que lee esto:**

- Basate solo en lo que dice este documento. Si algo no está acá, decí que no está documentado en lugar de inventarlo.
- Antes de escribir código, confirmá con el usuario el lenguaje que quiere usar, qué activos quiere seguir y qué datos necesita (puntas, profundidad, último precio y variación).
- Nunca escribas el usuario, la contraseña o el token dentro del código. Leelos de variables de entorno.
- Todo programa que escribas tiene que empezar con un bloque **Requisitos** que diga qué hay que instalar y el comando exacto (ver la sección 9). No des por hecho que el usuario ya tiene las librerías: si falta una, el programa falla con `ModuleNotFoundError` (Python) o `Cannot find package` (Node).
- La sección 8 lista los puntos que no están documentados. Respetala y avisale al usuario cuando el programa dependa de alguno.

---

## 1. Qué es y qué permite

El WebSocket de IOL es una conexión que se abre una sola vez y queda abierta. En lugar de consultar una y otra vez, el cliente se suscribe a los activos que le interesan y el servidor le envía cada novedad apenas ocurre.

- **Es solo de market data.** Sirve para seguir el mercado argentino y el de EE.UU. en tiempo real. No sirve para operar ni para consultar la cuenta: eso se hace por la REST API (`https://api.iolinversiones.com`).
- **Hay tres canales de datos.** Se piden con una clave distinta en el mensaje `subscribe` y llegan como un tipo de mensaje distinto:

| Canal (clave de `subscribe`) | Mensaje que llega | Qué trae | Cuándo llega | Límite |
|---|---|---|---|---|
| `quotes` | `type: "Q"` | Puntas: la mejor compra y la mejor venta, con la cantidad a cada precio. | Cuando cambia alguna punta. | 50 títulos por conexión. |
| `order_book` | `type: "B"` | Profundidad: las 5 mejores ofertas de compra y las 5 mejores de venta (hasta 5 de cada lado). | Cuando cambia el libro. | 1 título por conexión (comprobado en pruebas). Para seguir varios títulos, una conexión por título. |
| `trades` | `type: "T"` | Último precio operado, variación del día, cantidad y monto operados en el día. | Cuando hay una operación. Un título con poca liquidez puede pasar un rato sin mensajes. | 50 títulos por conexión. |

- **Se pueden combinar** los tres canales en una misma suscripción.
- **Último precio y variación:** vienen por `trades` (mensaje `T`), no por `quotes` ni por `order_book`. Los datos que no llegan por el WebSocket (apertura, máximo, mínimo y cierre anterior) se obtienen por la REST API: `GET /broker/market-data/{SYMBOL}/quote?market=BCBA&term=T0`. En la respuesta, el precio está en `data.prices.current`, la variación en `data.change.percent`, el volumen en `data.volume.shares` y el monto en `data.volume.amount`.

## 2. Datos de conexión

| Dato | Valor |
|---|---|
| Endpoint WebSocket | `wss://stream-marketdata.invertironline.com` |
| REST API (para obtener el token) | `https://api.iolinversiones.com` |
| Formato de los mensajes | JSON de texto, en ambos sentidos |

El dominio del WebSocket es `invertironline.com`, no `iolinversiones.com` (ese nombre no existe para el WebSocket y la conexión falla).

## 3. Recorrido completo de una conexión

1. **Obtener un token** con la REST API (o usar usuario y contraseña, ver el paso 3).
2. **Conectar** al endpoint WebSocket.
3. **Autenticar**, inmediatamente después de conectar y antes de cualquier otra cosa.
4. **Suscribirse** a los activos.
5. **Recibir datos** en tiempo real.
6. **Mantener la conexión** enviando un ping cada 15 segundos.
7. **Desconectar** de forma ordenada cuando se termina.

### Paso 1: obtener el token (REST)

Es el método recomendado para producción.

```
POST https://api.iolinversiones.com/auth/token
Content-Type: application/json

{
  "grant_type": "password",
  "username": "TU_USUARIO",
  "password": "TU_PASSWORD"
}
```

El usuario y la contraseña son los mismos de la plataforma o app de IOL (cuenta comitente activa). La respuesta trae el token en `data.access_token` y también un `refresh_token`.

- **El `access_token` vence a los 15 minutos.** Un programa que corre más tiempo tiene que renovarlo y reconectar.
- Para renovar el token se hace `POST /auth/token` con `{"grant_type": "refresh_token", "refresh_token": "..."}`. Según la documentación, el `refresh_token` vence a los 30 días.

### Paso 2: conectar

Abrir una conexión WebSocket a `wss://stream-marketdata.invertironline.com`. No hace falta mandar nada al conectar: el primer mensaje que se envía es el de autenticación.

### Paso 3: autenticar en el WebSocket

Hay dos formas. La recomendada para producción es con token.

**Con token (recomendado):**

```json
{ "action": "auth_token", "token": "TU_ACCESS_TOKEN" }
```

**Con credenciales (más simple):**

```json
{ "action": "auth", "username": "TU_USUARIO", "password": "TU_PASSWORD" }
```

Respuesta exitosa:

```json
{ "type": "Success", "code": 200, "msg": "Connected" }
```

Errores posibles: `400` si falta un parámetro y `401` si las credenciales o el token son inválidos o vencieron.

La autenticación se hace una vez por conexión. Si se abre otra conexión, hay que autenticarla también.

### Paso 4: suscribirse

Ver la sección 4 (cómo pedir los datos). Respuesta exitosa: `{ "type": "Success", "code": 200, "msg": "Subscribed" }`.

### Paso 5: recibir datos

Ver la sección 5 (mensajes que llegan).

### Paso 6: heartbeat (mantener la conexión)

El servidor **no envía pings**: el cliente es quien tiene que mandarlos.

- El cliente envía periódicamente `{ "action": "ping" }`. Recomendado: **cada 15 segundos**.
- El servidor responde `{ "type": "Success", "code": 200, "msg": "Pong" }`.
- Si el cliente no envía pings, el servidor cierra la conexión.

El ping es un mensaje JSON de texto como los demás. Si el programa cierra la conexión (o se reconecta), hay que detener el temporizador del ping para no seguir enviando sobre un socket cerrado. En cada conexión nueva se arranca un temporizador nuevo.

### Paso 7: desconectar

```json
{ "action": "disconnect" }
```

El servidor responde `{ "type": "Success", "code": 200, "msg": "Disconnecting" }` y luego cierra el socket.

## 4. Cómo pedir los datos

### Cómo se identifica un título

Cada activo se identifica con un string `SYMBOL|MARKET|TERM`, en mayúsculas y con las tres partes. Cada combinación es un título distinto y se suscribe por separado.

- `SYMBOL`: el ticker del activo.
- `MARKET`: el mercado. Mercado argentino: `BCBA`. Mercados de EE.UU.: `NYSE`, `NASDAQ` y `AMEX`.
- `TERM`: el plazo. `T0` es contado inmediato y `T1` es 24 hs. Qué plazo corresponde depende del tipo de activo.

| Qué querés seguir | Cómo se pide | Ejemplo |
|---|---|---|
| Acción argentina | ticker, `BCBA`, plazo | `GGAL|BCBA|T0` |
| Bono | ticker, `BCBA`, plazo | `AL30|BCBA|T0` |
| CEDEAR en pesos | ticker del CEDEAR, `BCBA`, plazo | `AAPL|BCBA|T0` |
| CEDEAR en dólar MEP | ticker con sufijo `D` | `NUD|BCBA|T1` |
| CEDEAR en dólar cable | ticker con sufijo `C` | `NUC|BCBA|T1` |
| Activo de EE.UU. | ticker, mercado (`NYSE`, `NASDAQ` o `AMEX`), plazo `T1` | `NU|NYSE|T1` |

| Tipo de activo | Plazos |
|---|---|
| Acciones, CEDEARs, obligaciones negociables (ON), letras y bonos | `T0` o `T1` |
| Opciones | solo `T1` |
| Todo lo de EE.UU. | solo `T1` |

- **La moneda se elige con el ticker, no con un campo aparte.** Para seguir un activo en pesos, en dólar MEP y en dólar cable hay que suscribirse a tres tickers distintos (por ejemplo `NU`, `NUD` y `NUC`) y distinguirlos por el campo `S` del mensaje.
- **El mismo ticker puede existir en dos mercados** (por ejemplo `NU` como CEDEAR en `BCBA` y como acción en `NYSE`). Son dos títulos distintos y el campo `M` del mensaje los diferencia.
- **Plazo inválido: no hay error.** Un activo con un plazo que no corresponde a su tipo (por ejemplo `NU|NYSE|T0`) responde `Subscribed` y después nunca manda datos. Si no llegan datos en horario de mercado, lo primero que hay que revisar es el plazo.
- **Para identificar cada mensaje**, usá siempre juntos `S` (símbolo), `M` (mercado) y `T` (plazo) como clave, no solo el símbolo.

### Reglas del mensaje `subscribe`

**Las tres claves son obligatorias: `trades`, `quotes` y `order_book`.** Las que no se usan van como array vacío (`[]`). Si falta alguna, el servidor responde `400 Argument Error`.

### Pedir un solo título

```json
{
  "action": "subscribe",
  "trades": [],
  "quotes": ["GGAL|BCBA|T0"],
  "order_book": []
}
```

### Pedir varios títulos

`quotes` y `trades` aceptan una lista: una conexión puede seguir hasta 50 títulos en cada uno. `order_book` es la excepción: acepta un solo título por conexión (ver más abajo).

```json
{
  "action": "subscribe",
  "trades": [],
  "quotes": ["GGAL|BCBA|T0", "AL30|BCBA|T0", "NUD|BCBA|T1"],
  "order_book": []
}
```

### Pedir varios tipos de datos a la vez

Los canales se pueden combinar en el mismo mensaje. Para tener puntas y último precio y variación de los mismos títulos:

```json
{
  "action": "subscribe",
  "trades": ["GGAL|BCBA|T0", "AL30|BCBA|T0"],
  "quotes": ["GGAL|BCBA|T0", "AL30|BCBA|T0"],
  "order_book": []
}
```

Los mensajes llegan por separado: un `Q` cuando cambian las puntas y un `T` cuando hay una operación.

### Pedir la profundidad (`order_book`)

`order_book` acepta **un solo título por conexión**. Se pide igual que los otros canales, pero con un único título en la lista:

```json
{
  "action": "subscribe",
  "trades": [],
  "quotes": [],
  "order_book": ["GGAL|BCBA|T0"]
}
```

Si se pide más de un título de `order_book` en la misma conexión, ya sea en un mismo mensaje o en mensajes separados, el servidor rechaza la suscripción y responde (y rechaza el mensaje completo, también los `quotes` y `trades` que viajaran en él):

```json
{ "type": "Error", "code": 401, "msg": "Order Book Subscribed Exceded" }
```

Ese `401` no significa que el token haya vencido: no hay que renovarlo. Hay que dejar un solo título de `order_book` en esa conexión y pedir los demás en otras conexiones.

### Pedir la profundidad de varios títulos

Para seguir la profundidad de N títulos hay que abrir **N conexiones**, una por título. Cada una se autentica y se suscribe por separado, y todas pueden estar activas al mismo tiempo (en una prueba funcionaron 8 a la vez).

### Pedir más de 50 títulos

El límite de 50 es de cada conexión, en `quotes` y en `trades`. Si el usuario necesita más, hay que abrir otra conexión (otro WebSocket, en el mismo programa o en uno nuevo), repartir los activos entre ellas, y autenticar y suscribir cada una por separado.

### Desuscribirse

Cancelar activos puntuales (usa los mismos campos que `subscribe`). **No se verificó** si `unsubscribe` también exige las tres claves; por las dudas, mandalas todas:

```json
{ "action": "unsubscribe", "trades": [], "quotes": ["CLDR|BCBA|T0"], "order_book": [] }
```

Cancelar todo de una vez (útil antes de desconectar o para empezar de cero):

```json
{ "action": "unsubscribe_all" }
```

Ambas responden `{ "type": "Success", "code": 200, "msg": "Unsubscribed" }`.

## 5. Mensajes que llegan

Los mensajes de datos llegan con esta estructura general:

```json
{ "type": "<tipo>", "code": 200, "msg": { ... } }
```

Los datos van **siempre dentro de `msg`**. Todos los mensajes de datos traen `S` (símbolo), `M` (mercado), `T` (plazo) y `D` (fecha y hora ISO 8601 con offset horario, por ejemplo `-03:00`, no en UTC).

### Puntas: `type: "Q"` (canal `quotes`)

```json
{
  "type": "Q",
  "code": 200,
  "msg": {
    "S": "GGAL",
    "M": "BCBA",
    "T": "T1",
    "V": [
      { "T": "BID", "X": 756, "P": 6025, "N": 1 },
      { "T": "OFFER", "X": 2101, "P": 6030, "N": 1 }
    ],
    "D": "2026-10-23T13:07:38.7388217-03:00"
  }
}
```

| Campo | Significado |
|---|---|
| `V` | Array de niveles de precio: la mejor compra y la mejor venta |
| `V[].T` | `"BID"` (compra) o `"OFFER"` (venta) |
| `V[].X` | Cantidad disponible a ese precio |
| `V[].P` | Precio del bid u offer |
| `V[].N` | Número de nivel dentro de su lado (`1` = mejor precio). En `Q` siempre vale `1` |

### Profundidad: `type: "B"` (canal `order_book`)

Tiene la misma estructura que `Q`, pero `V` trae las 5 mejores ofertas de compra y las 5 mejores de venta (hasta 5 de cada lado). `N` es la posición de la oferta dentro de su lado y va de `1` (el mejor precio: el bid más alto o el offer más bajo) hasta `5`. Mensaje real recibido el 23/10/2026:

```json
{
  "type": "B",
  "code": 200,
  "msg": {
    "S": "GGAL",
    "M": "BCBA",
    "T": "T0",
    "V": [
      { "T": "BID", "X": 1550, "P": 6005, "N": 1 },
      { "T": "BID", "X": 5582, "P": 6000, "N": 2 },
      { "T": "BID", "X": 1, "P": 5985, "N": 3 },
      { "T": "BID", "X": 21, "P": 5980, "N": 4 },
      { "T": "BID", "X": 26, "P": 5970, "N": 5 },
      { "T": "OFFER", "X": 991, "P": 6025, "N": 1 },
      { "T": "OFFER", "X": 2771, "P": 6030, "N": 2 },
      { "T": "OFFER", "X": 100, "P": 6060, "N": 3 },
      { "T": "OFFER", "X": 400, "P": 6065, "N": 4 },
      { "T": "OFFER", "X": 795, "P": 6070, "N": 5 }
    ],
    "D": "2026-10-23T13:07:35.4006382-03:00"
  }
}
```


### Operaciones: `type: "T"` (canal `trades`)

```json
{
  "type": "T",
  "code": 200,
  "msg": {
    "S": "AL30",
    "M": "BCBA",
    "T": "T0",
    "P": 85650,
    "X": 42972,
    "TS": 83983741,
    "TP": 71872519819.3,
    "V": -0.05,
    "D": "2026-10-23T13:12:14-03:00"
  }
}
```

| Campo | Significado |
|---|---|
| `P` | Último precio operado |
| `V` | Variación porcentual del día (`-0.05` significa −0,05 %) |
| `TS` | Cantidad operada en el día (nominales), acumulada: crece con cada operación |
| `TP` | Monto operado en el día, acumulado |
| `X` | Valor que acompaña a cada operación. Coincide con `volume.shares` de la REST API. Su significado exacto no está documentado |

`D` en este mensaje llega sin fracciones de segundo. Con operaciones en un bono, el monto se relaciona con los nominales y el precio así: monto = nominales × precio / 100.

## 6. Errores

Todos los errores tienen el mismo formato:

```json
{ "type": "Error", "code": 401, "msg": "Authentication Error" }
```

| Código | Mensaje | Qué significa | Qué hacer |
|---|---|---|---|
| 400 | Argument Error | Falta un campo o el formato es inválido. | En `subscribe`, revisar primero que estén las tres claves (`trades`, `quotes`, `order_book`). Después, revisar el mensaje enviado. |
| 401 | Authentication Error | Credenciales inválidas o token vencido. | Renovar el token. No reintentar en bucle con los mismos datos. |
| 401 | Order Book Subscribed Exceded | Se pidió más de un título de `order_book` en la misma conexión. No es un problema de token. | No renovar el token. Dejar un solo título de `order_book` por conexión y abrir otra conexión por cada título adicional. |
| 403 | Forbidden | Sin permisos. | No reintentar. Avisarle al usuario que contacte a soporte. |
| 404 | Not Found | El activo no existe. | Verificar el formato `SYMBOL|MARKET|TERM`. |
| 429 | Too Many Requests | Demasiados mensajes en poco tiempo. | Esperar unos segundos y enviar menos mensajes. |
| 500 | Internal Server Error | Error del servidor. | Esperar unos segundos y reintentar, esperando un poco más en cada intento. |

El `400` solo dice `Argument Error`: no indica qué campo falla ni qué activo lo causó.

### Situaciones que el programa tiene que manejar

| Situación | Qué hacer |
|---|---|
| El `subscribe` responde `400` | Revisar que el mensaje tenga `trades`, `quotes` y `order_book`. Es la causa más común. |
| El `subscribe` responde `401` con `Order Book Subscribed Exceded` | Dejar un solo título de `order_book` en esa conexión y abrir otra conexión por cada título adicional. |
| Se suscribe y no llegan datos, sin ningún error | Puede ser que el mercado esté cerrado, que el título no tenga operaciones (en `trades`), o que el plazo no corresponda al mercado (por ejemplo `T0` en EE.UU.). Un plazo inválido responde `Subscribed` pero nunca manda datos. |
| Hay que saber qué activo falla | Suscribir de a un activo, porque el error no dice cuál fue. |
| `401` al autenticar | Renovar el token (REST) y volver a conectar. Si usa usuario y contraseña, avisar al usuario que los revise. No reintentar solo. |
| La conexión se cierra sola | Una causa conocida es que el cliente no envía pings: revisar que el heartbeat esté activo. Si el cierre es otro, reconectar con espera creciente y volver a autenticar y suscribir. |
| El token vence con la conexión abierta | El token dura 15 minutos: renovarlo antes de que venza y reconectar. |
| Llega un mensaje con `type: "Error"` | Registrarlo (con el mensaje completo) y seguir según la tabla de códigos. |

## 7. Reglas para generar código

Cuando le pidas ejemplos a la IA, estas son las reglas que tiene que seguir:

1. Las credenciales y el token se leen de variables de entorno (`IOL_USERNAME`, `IOL_PASSWORD` o `IOL_TOKEN`). Nunca van escritas en el código. Como el token dura 15 minutos, un programa que corre más tiempo debe pedir el token por REST con usuario y contraseña, y volver a pedirlo en cada reconexión.
2. Siempre se autentica primero. No se manda ningún `subscribe` antes de recibir `Connected`.
   El mensaje `subscribe` siempre lleva las tres claves (`trades`, `quotes` y `order_book`), con `[]` en las que no se usan.
3. Se mantiene la conexión con un heartbeat: el cliente envía `{"action": "ping"}` cada 15 segundos y el servidor responde `Pong`. El servidor no manda pings.
4. Se maneja el cierre inesperado de la conexión: reconectar con espera creciente, y al reconectar volver a autenticar y volver a suscribir (tratá cada conexión nueva como vacía).
5. Se valida que el programa no pase de 50 títulos por conexión en `quotes` y en `trades`. Si hay más, se reparten en varias conexiones. El `order_book` acepta un solo título por conexión: para la profundidad de varios títulos se abre una conexión por título. Si responde `401 Order Book Subscribed Exceded`, es porque se pidió más de un título de `order_book` en la misma conexión.
6. Se registran (log) los mensajes con `type: "Error"`.
7. Los activos van en una lista configurable (no escritos a mano en el medio del código), siempre con el formato `SYMBOL|MARKET|TERM` en mayúsculas.
8. Para el último precio y la variación se usa el canal `trades` (mensaje `T`); no hace falta consultar la REST API para eso.
9. Fuera del horario de mercado puede que no lleguen datos. Eso no es un error.
10. Los datos se leen siempre de `msg`, y cada mensaje se identifica con `S` + `M` + `T` juntos (así se distinguen el mismo ticker en distintos mercados, plazos o monedas).
11. Cada programa se entrega con sus **requisitos** arriba (librerías y comando de instalación) y con el comando para ejecutarlo. Ver la sección 9.

## 8. Puntos no documentados

Los puntos de esta sección **no están documentados**. No inventes la respuesta: si el programa depende de alguno, decíselo al usuario y proponé probarlo con su conexión real.

- **Significado exacto del campo `X`** del mensaje `T`. Se sabe que coincide con `volume.shares` de la REST API.
- **Cuántas conexiones simultáneas admite el servidor por usuario.** En pruebas se abrieron hasta 8 a la vez (una de `quotes` y `trades` y siete de `order_book`) y funcionaron. No se probó cuál es el tope.
- **Cambiar el título de `order_book` en una conexión.** No se probó si, después de un `unsubscribe` del libro, se puede pedir otro título por la misma conexión.
- **Cuenta del límite de 50.** No dice si el mismo activo en `quotes` y en `trades` cuenta como 1 o como 2 títulos.
- **`unsubscribe` y las tres claves.** No se probó si exige también `trades`, `quotes` y `order_book`. Mandalas siempre.
- **Errores por activo.** Los errores del `400` solo dicen `Argument Error`, sin indicar qué campo falla. Los errores no indican qué activo los causó, ni se sabe si falla toda la suscripción o solo ese activo. Para saber cuál falla, suscribí de a uno.
- **Mensaje inicial.** No dice si al suscribirse llega una foto inicial de las puntas o si hay que esperar a que algo cambie.
- **Activos de EE.UU.** No se confirmó qué canales mandan datos para todos los activos de EE.UU. (por ejemplo `NU|NYSE|T1`). En una prueba, el `order_book` de EWZ (NYSE), GFS (NASDAQ) y PAGS (NYSE) trajo un solo nivel, mientras que el de títulos argentinos trajo cinco; LIT y PBR (NYSE) no mandaron datos, y NU (NYSE) mandó solo `trades`. Si una suscripción de EE.UU. no manda datos, probar los otros canales y avisar al usuario.
- **Vencimiento del token con la conexión abierta.** No dice qué pasa con una conexión abierta cuando vence el `access_token` (15 minutos). Lo previsto es renovar el token y reconectar antes de que venza.
- **`auth` con usuario y contraseña.** Está documentado, pero esta guía solo verificó la autenticación con `auth_token`.

## 9. Ejemplos de programas

### Requisitos antes de ejecutar

Hay que instalar las librerías una sola vez, antes de correr cualquier ejemplo.

**Python (ejemplos A, C y D):**

```bash
python3 -m pip install websockets requests
```

- Usá `python3 -m pip` y no `pip` a secas: así la librería se instala en el mismo Python que después ejecuta el script. Con `pip` solo puede quedar instalada en otro Python y el error `ModuleNotFoundError: No module named 'websockets'` sigue apareciendo.
- Si el sistema no deja instalar de forma global, agregá `--user` (`python3 -m pip install --user websockets requests`) o usá un entorno virtual.
- En macOS, el Python que trae el sistema puede mostrar un aviso `NotOpenSSLWarning` de `urllib3`. Es solo una advertencia: no impide que el programa funcione.
- Ejecutar: `python3 nombre_del_archivo.py`

**Node.js (ejemplo B):**

```bash
npm install ws
```

- El archivo se llama `.mjs` (o el `package.json` tiene `"type": "module"`), porque usa `import`.
- Ejecutar: `node nombre_del_archivo.mjs`

**Variables de entorno:** hay que definirlas en la terminal antes de ejecutar. Los ejemplos A y D leen `IOL_USERNAME` y `IOL_PASSWORD` (o `IOL_TOKEN`, si ya tenés un token vigente; el ejemplo A igual necesita usuario y contraseña para reconectar, porque el token vence a los 15 minutos); el ejemplo B lee `IOL_TOKEN` (el `access_token`); el ejemplo C lee `IOL_USERNAME` y `IOL_PASSWORD`. Por ejemplo: `export IOL_TOKEN="tu_access_token"` (en Windows PowerShell: `$env:IOL_TOKEN="tu_access_token"`). Recordá que el token dura 15 minutos.

### Ejemplo A: Python, puntas y último precio de varios activos (con reconexión)

Pide `quotes` y `trades` de los mismos títulos en un solo `subscribe`, espera `Connected` antes de suscribirse y, al reconectar, pide un token nuevo por REST con `IOL_USERNAME` e `IOL_PASSWORD`. El `IOL_TOKEN` del entorno (si lo definís) se usa solo en la primera conexión, porque a los 15 minutos ya está vencido.

```python
import asyncio
import json
import os

import requests
import websockets

WS_URL = "wss://stream-marketdata.invertironline.com"
API_URL = "https://api.iolinversiones.com"
# Formato SYMBOL|MARKET|TERM, máximo 50 por conexión. Otros ejemplos:
#   "NUD|BCBA|T1"  CEDEAR en dólar MEP     "NU|NYSE|T1"  acción de EE.UU.
ACTIVOS = ["GGAL|BCBA|T0", "AL30|BCBA|T0"]


class AuthError(Exception):
    pass


def obtener_token(primera_vez):
    # El IOL_TOKEN del entorno solo sirve para la primera conexión: a los 15 minutos
    # está vencido. En cada reconexión se pide un token nuevo por REST.
    if primera_vez and os.environ.get("IOL_TOKEN"):
        return os.environ["IOL_TOKEN"]
    if not (os.environ.get("IOL_USERNAME") and os.environ.get("IOL_PASSWORD")):
        raise AuthError("Para renovar el token hay que definir IOL_USERNAME y IOL_PASSWORD")
    r = requests.post(f"{API_URL}/auth/token", json={
        "grant_type": "password",
        "username": os.environ["IOL_USERNAME"],
        "password": os.environ["IOL_PASSWORD"],
    }, timeout=15)
    r.raise_for_status()
    return r.json()["data"]["access_token"]


async def heartbeat(ws):
    # El servidor no envía pings: el cliente los manda cada 15 segundos
    while True:
        await asyncio.sleep(15)
        await ws.send(json.dumps({"action": "ping"}))


async def escuchar(primera_vez):
    token = obtener_token(primera_vez)
    async with websockets.connect(WS_URL, ping_interval=None) as ws:
        pulso = asyncio.create_task(heartbeat(ws))
        try:
            await recibir(ws, token)
        finally:
            pulso.cancel()


async def recibir(ws, token):
    # 1. Autenticar. El subscribe se envía recién al recibir "Connected".
    await ws.send(json.dumps({"action": "auth_token", "token": token}))
    ultimo = {}  # clave "S|M|T" -> último mensaje T

    async for raw in ws:
        message = json.loads(raw)

        # Respuesta al ping del heartbeat
        if message.get("type") == "Success" and message.get("msg") == "Pong":
            continue

        if message.get("type") == "Error":
            print("Error:", message)
            if message.get("code") == 401 and message.get("msg") == "Authentication Error":
                raise AuthError("Token inválido o vencido")
            continue

        # 2. Autenticado: recién ahora suscribirse (quotes y trades juntos)
        if message.get("type") == "Success" and message.get("msg") == "Connected":
            await ws.send(json.dumps({"action": "subscribe", "trades": ACTIVOS, "quotes": ACTIVOS, "order_book": []}))
            continue

        # 3. Datos. Cada mensaje se identifica con S + M + T juntos.
        payload = message.get("msg")
        if not isinstance(payload, dict):
            continue
        clave = f'{payload.get("S")}|{payload.get("M")}|{payload.get("T")}'
        if message.get("type") == "Q":
            niveles = payload.get("V", [])
            compras = [n["P"] for n in niveles if n.get("T") == "BID"]
            ventas = [n["P"] for n in niveles if n.get("T") == "OFFER"]
            # La mejor compra es el precio más alto; la mejor venta, el más bajo
            print(clave, "compra:", max(compras, default=None), "venta:", min(ventas, default=None))
        elif message.get("type") == "T":
            ultimo[clave] = payload
            print(clave, "último:", payload.get("P"), "variación %:", payload.get("V"),
                  "nominales:", payload.get("TS"), "monto:", payload.get("TP"))


async def main():
    intentos = 0
    primera_vez = True
    while True:
        try:
            await escuchar(primera_vez)
            motivo = "el servidor cerró la conexión"
        except AuthError:
            raise  # no reintentar con el mismo token: hay que pedir uno nuevo
        except (websockets.ConnectionClosed, OSError) as e:
            motivo = f"conexión caída ({e})"
        # Siempre se espera antes de reconectar (espera creciente, máximo 30 s)
        espera = min(2 ** intentos, 30)
        intentos += 1
        print(f"{motivo}. Reintentando en {espera} s...")
        await asyncio.sleep(espera)
        primera_vez = False


asyncio.run(main())
```

### Ejemplo B: Node.js, puntas y último precio con reconexión

Requiere `npm install ws` (ver Requisitos) y archivo `.mjs`. Espera `Connected` antes de suscribirse. Como lee `IOL_TOKEN` del entorno, al vencer el token (15 minutos) hay que reiniciarlo con un token nuevo.

```javascript
import WebSocket from "ws";

const WS_URL = "wss://stream-marketdata.invertironline.com";
// access_token obtenido por REST (dura 15 minutos). Se lee una sola vez: si el programa
// se reconecta cuando el token ya venció, el servidor responde 401 y el programa se detiene.
const TOKEN = process.env.IOL_TOKEN;
// Formato SYMBOL|MARKET|TERM, máximo 50 por conexión. Otros ejemplos:
//   "NUD|BCBA|T1"  CEDEAR en dólar MEP     "NU|NYSE|T1"  acción de EE.UU.
const ACTIVOS = ["GGAL|BCBA|T0", "AL30|BCBA|T0"];

let intentos = 0;

function conectar() {
  const ws = new WebSocket(WS_URL);
  let reconectar = true;
  let pulso;

  ws.on("open", () => {
    // Autenticar. El subscribe se envía recién al recibir "Connected".
    ws.send(JSON.stringify({ action: "auth_token", token: TOKEN }));
    // El servidor no envía pings: el cliente los manda cada 15 segundos
    pulso = setInterval(() => ws.send(JSON.stringify({ action: "ping" })), 15000);
  });

  ws.on("message", (data) => {
    const message = JSON.parse(data.toString());

    // Respuesta al ping del heartbeat
    if (message.type === "Success" && message.msg === "Pong") return;

    if (message.type === "Error") {
      console.error("Error:", message);
      if (message.code === 401 && message.msg === "Authentication Error") {
        reconectar = false; // no reintentar: hay que renovar el token
        ws.close();
      }
      return;
    }

    // Autenticado: recién ahora suscribirse (quotes y trades juntos)
    if (message.type === "Success" && message.msg === "Connected") {
      intentos = 0;
      ws.send(JSON.stringify({ action: "subscribe", trades: ACTIVOS, quotes: ACTIVOS, order_book: [] }));
      return;
    }

    const p = message.msg;
    if (!p || typeof p !== "object") return;
    const clave = `${p.S}|${p.M}|${p.T}`; // cada mensaje se identifica con S + M + T
    if (message.type === "Q" && Array.isArray(p.V)) {
      const compras = p.V.filter((n) => n.T === "BID").map((n) => n.P);
      const ventas = p.V.filter((n) => n.T === "OFFER").map((n) => n.P);
      // La mejor compra es el precio más alto; la mejor venta, el más bajo
      // Si un lado viene vacío, Math.max/Math.min devolverían -Infinity/Infinity
      const mejorCompra = compras.length ? Math.max(...compras) : null;
      const mejorVenta = ventas.length ? Math.min(...ventas) : null;
      console.log(clave, "compra:", mejorCompra, "venta:", mejorVenta);
    } else if (message.type === "T") {
      console.log(clave, "último:", p.P, "variación %:", p.V, "nominales:", p.TS, "monto:", p.TP);
    }
  });

  ws.on("close", () => {
    clearInterval(pulso);
    if (!reconectar) return;
    // Reconectar con espera creciente (máximo 30 s); al reabrir se vuelve a autenticar y suscribir
    const espera = Math.min(1000 * 2 ** intentos++, 30000);
    console.log(`Conexión cerrada. Reintentando en ${espera / 1000} s...`);
    setTimeout(conectar, espera);
  });

  ws.on("error", (err) => console.error("Error de socket:", err.message));
}

conectar();
```

### Ejemplo C: obtener el token por REST (Python)

Requiere `python3 -m pip install requests` (ver Requisitos).

```python
import os
import requests

API_URL = "https://api.iolinversiones.com"

response = requests.post(f"{API_URL}/auth/token", json={
    "grant_type": "password",
    "username": os.environ["IOL_USERNAME"],
    "password": os.environ["IOL_PASSWORD"],
})
response.raise_for_status()
token = response.json()["data"]["access_token"]
```

### Ejemplo D: Python, profundidad de varios títulos

Muestra las 5 mejores ofertas de compra y de venta de varios títulos. Como `order_book` acepta un solo título por conexión, abre una conexión por título (todas con el mismo token) y las va abriendo de a una, con un segundo de diferencia. Cada mensaje se identifica con símbolo, mercado y plazo (`S`, `M`, `T`). Si el servidor responde `401 Order Book Subscribed Exceded`, es porque se pidió más de un título de `order_book` en una misma conexión (ver la sección 4).

```python
import asyncio
import json
import os

import requests
import websockets

WS_URL = "wss://stream-marketdata.invertironline.com"
API_URL = "https://api.iolinversiones.com"
# Formato SYMBOL|MARKET|TERM. order_book acepta un solo título por conexión,
# por eso se abre una conexión por cada título de la lista.
ACTIVOS = ["GGAL|BCBA|T0", "AL30|BCBA|T0", "NUD|BCBA|T1"]


def obtener_token():
    if os.environ.get("IOL_TOKEN"):
        return os.environ["IOL_TOKEN"]
    r = requests.post(f"{API_URL}/auth/token", json={
        "grant_type": "password",
        "username": os.environ["IOL_USERNAME"],
        "password": os.environ["IOL_PASSWORD"],
    }, timeout=15)
    r.raise_for_status()
    return r.json()["data"]["access_token"]


async def heartbeat(ws):
    while True:
        await asyncio.sleep(15)
        await ws.send(json.dumps({"action": "ping"}))


async def seguir_libro(activo, token, demora):
    await asyncio.sleep(demora)  # las conexiones se abren de a una
    async with websockets.connect(WS_URL, ping_interval=None) as ws:
        pulso = asyncio.create_task(heartbeat(ws))
        try:
            await ws.send(json.dumps({"action": "auth_token", "token": token}))
            async for raw in ws:
                message = json.loads(raw)
                tipo = message.get("type")
                if tipo == "Success" and message.get("msg") == "Connected":
                    await ws.send(json.dumps({"action": "subscribe", "trades": [], "quotes": [], "order_book": [activo]}))
                elif tipo == "Error":
                    print(activo, "Error:", message)
                    return
                elif tipo == "B":
                    p = message["msg"]
                    niveles = p.get("V", [])
                    # Se alinea por número de nivel (N): un lado puede traer menos de 5 niveles
                    compras = {n["N"]: n for n in niveles if n["T"] == "BID"}
                    ventas = {n["N"]: n for n in niveles if n["T"] == "OFFER"}
                    print(f'\n{p["S"]}|{p["M"]}|{p["T"]}')
                    for nivel in sorted(set(compras) | set(ventas)):
                        c, v = compras.get(nivel), ventas.get(nivel)
                        compra = f'{c["X"]} @ {c["P"]}' if c else "-"
                        venta = f'{v["X"]} @ {v["P"]}' if v else "-"
                        print(f'  nivel {nivel}: compra {compra}   venta {venta}')
        finally:
            pulso.cancel()


async def main():
    token = obtener_token()
    await asyncio.gather(*(seguir_libro(a, token, i) for i, a in enumerate(ACTIVOS)))


asyncio.run(main())
```

## 10. Pedidos de ejemplo para hacerle a la IA

- "Escribime un script en Python que muestre en la terminal la mejor compra y venta de GGAL en tiempo real."
- "Armame un programa que muestre, para GGAL y AL30, el último precio, la variación y la mejor compra y venta, y se actualice solo."
- "Armame una página HTML que muestre la profundidad (5 mejores ofertas de compra y venta) de AL30 y se actualice sola."
- "Quiero ver la profundidad de 5 activos a la vez."
- "Hacé un programa en Node.js que siga 10 activos y me avise por consola cuando el último precio supere un valor que yo defina."
- "Quiero seguir NU en pesos, en dólar MEP y en dólar cable, y mostrar los tres últimos precios lado a lado."
- "Agregá reconexión automática y manejo de errores a este programa."

## 11. Más información

- Documentación del WebSocket: https://developers.iolinversiones.com/docs/websocket
- Tutorial de tiempo real: https://developers.iolinversiones.com/docs/quickstart/realtime
- Autenticación (tokens y renovación): https://developers.iolinversiones.com/docs/auth
