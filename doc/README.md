# pyIol2 Documentation

Esta carpeta reune la documentacion y los ejemplos de `pyIol2`, el cliente
Python no oficial de la API v1 de IOL Inversiones (REST + WebSocket de market
data).

## Por Donde Empezar

- **[Guia para agentes](./agent-guide.md)** — instalacion, autenticacion,
  diferencias entre el cliente sync y el streaming, manejo de errores con
  `trace_id`, ciclo de vida del WebSocket y reglas de seguridad para escribir
  en la cuenta.
- **[Referencia de la API](./api-reference.md)** — todos los metodos publicos
  con firma, argumentos, retorno y notas, mas el catalogo de modelos.
- **[Recetas](./recipes/)** — scripts cortos y ejecutables, de solo lectura
  salvo la estimacion.
- **[Notebooks](./notebooks/)** — recorrido paso a paso, commiteado sin ejecutar.
- **[Contrato de la API v1](./vendor/iol-api-v1.md)** — snapshot de la
  documentacion que publica IOL; la fuente de los nombres de campos.

## Notas de la API v1

La API v1 responde siempre con el sobre `{meta, data, error}`:

- `data` trae el recurso o `null` si hubo error.
- `error` trae `message`, `code` y `details`.
- `meta.trace_id` identifica la request y es el dato que pide el soporte de IOL.
  La libreria lo expone en `IOLAPIError.trace_id`.

Diferencias con la API v2 (`py_iol`) que mas rompen al migrar:

| Tema | v2 (`py_iol`) | v1 (`pyIol2`) |
|------|---------------|---------------|
| Host | `api.invertironline.com` | `api.iolinversiones.com` |
| Mercado | `"bCBA"` | `"BCBA"` |
| Plazos | `t0`..`t3`, default `t1` | `T0`, `T1`, default `T0` |
| Pais | `"argentina"` | `"AR"` |
| Eventos en tiempo real | no hay | WebSocket de market data |

## Recetas

| Script | Que muestra |
|--------|-------------|
| [`quote.py`](./recipes/quote.py) | Cotizacion de mercado y profundidad del libro |
| [`historical_bars.py`](./recipes/historical_bars.py) | Serie OHLCV de un rango de fechas |
| [`positions.py`](./recipes/positions.py) | Saldos, posiciones e historial de patrimonio |
| [`estimate_order.py`](./recipes/estimate_order.py) | Estimacion de costos, sin efectos |
| [`stream_quotes.py`](./recipes/stream_quotes.py) | Streaming con un tope de mensajes |

Todas leen `IOL_USERNAME` e `IOL_PASSWORD` del entorno:

```bash
export IOL_USERNAME=tu_usuario_iol
export IOL_PASSWORD=tu_password_iol

uv run python doc/recipes/quote.py
```

## Notebooks

La carpeta `notebooks/` tiene notebooks de Jupyter listos para ejecutar en tu
cuenta, con las credenciales tomadas del entorno.

| Notebook | Contenido |
|----------|-----------|
| [01_autenticacion.ipynb](./notebooks/01_autenticacion.ipynb) | Credenciales, cliente, estado del servicio y permisos |
| [02_cotizaciones.ipynb](./notebooks/02_cotizaciones.ipynb) | Cotizacion, profundidad, screener, opciones e historicos |
| [03_streaming.ipynb](./notebooks/03_streaming.ipynb) | WebSocket asincronico, canales y limites |
| [04_cuenta_y_ordenes.ipynb](./notebooks/04_cuenta_y_ordenes.ipynb) | Saldos, posiciones, operaciones y estimacion de ordenes |

### Como ejecutarlos

```bash
# Dependencias de desarrollo (incluye jupyter y python-dotenv)
uv sync --all-extras

cd doc/notebooks
uv run jupyter notebook
```

O abrirlos en VS Code con la extension de Jupyter.

### Reglas

- Se commitean **sin ejecutar**: `execution_count: null` y `outputs: []`.
- El kernel es `python3`.
- Las credenciales se leen de `os.environ`; el placeholder se marca con
  `# completar`.
- Las operaciones que mueven dinero quedan **comentadas** y marcadas como
  tales. Verificar dos veces antes de descomentarlas.
- Para mirar sin riesgo, usar las recetas de solo lectura o la estimacion.

## Distribucion

`doc/` y `odd/` estan excluidos del sdist y la wheel empaqueta solo `pyIol2`:
estos Markdown son documentacion del repositorio, no del paquete instalado. Si
necesitas la referencia desde una instalacion de `pyiol2-client`, mira los
docstrings del codigo.

## Contribuir a la Documentacion

1. Verifica el nombre, el default y el tipo en el codigo antes de escribirlos.
2. Mantene una seccion por metodo, en el orden de `pyIol2/client.py`.
3. Actualiza este indice si agregas o renombras un archivo.
4. Corre `uv run ruff check doc/recipes/` y
   `uv run ruff format --check doc/recipes/` antes del Pull Request.
