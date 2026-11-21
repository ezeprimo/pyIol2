# Guia de Contribucion

Gracias por tu interes en contribuir a `pyiol2-client`. Esta guia explica el
entorno de desarrollo, las convenciones y el flujo de ramas y releases.

## Tabla de Contenidos

- [Requisitos](#requisitos)
- [Configuracion del Entorno](#configuracion-del-entorno)
- [Comandos del Proyecto](#comandos-del-proyecto)
- [Estandares de Codigo](#estandares-de-codigo)
- [Tests](#tests)
- [Commits](#commits)
- [Flujo de Ramas](#flujo-de-ramas)
- [Versionado y Releases](#versionado-y-releases)
- [Documentacion](#documentacion)

---

## Requisitos

- **Python >= 3.10** (el piso mas bajo que declara `pyproject.toml`).
- [uv](https://docs.astral.sh/uv/) como gestor de paquetes y de entorno.
- Git.
- Cuenta de IOL con la API habilitada, solo para pruebas manuales.

## Configuracion del Entorno

```bash
# Clonar el repositorio
git clone https://github.com/ezeprimo/pyIol2.git
cd pyIol2

# Instalar el paquete y todas las dependencias de desarrollo (ruff, pytest,
# pytest-asyncio, pytest-cov, jupyter, python-dotenv)
uv sync --all-extras
```

Las credenciales para pruebas manuales van por entorno, nunca en un archivo
versionado:

```bash
# Linux / macOS
export IOL_USERNAME=tu_usuario_iol
export IOL_PASSWORD=tu_password_iol

# Windows PowerShell
$env:IOL_USERNAME = "tu_usuario_iol"
$env:IOL_PASSWORD = "tu_password_iol"
```

Si preferis un `.env` local, esta ignorado por git; no lo commitees ni lo uses
en tests.

## Comandos del Proyecto

```bash
# Lint
uv run ruff check pyIol2/ tests/

# Formato
uv run ruff format pyIol2/ tests/

# Verificar formato sin escribir (lo que corre el CI)
uv run ruff format --check pyIol2/ tests/

# Tests
uv run pytest tests/ -q

# Tests con cobertura
uv run pytest tests/ -q --cov=pyIol2

# Documentacion: recetas
uv run ruff check doc/recipes/
uv run ruff format --check doc/recipes/

# Build del paquete
uv build

# Los helpers de `scripts/` tambien se lintean en el workflow de publicacion
uv run ruff check scripts/
uv run ruff format --check scripts/
```

Los tests no necesitan credenciales ni red: usan `httpx.MockTransport` y un
conector de WebSocket falso.

## Estandares de Codigo

Ruff es la unica herramienta de estilo. La configuracion vive en
`pyproject.toml`:

- `line-length = 100`.
- Reglas `E`, `W`, `F`, `I` (isort), `B` (bugbear), `C4`, `UP`.
- `known-first-party = ["pyIol2"]`.

Reglas de la casa:

1. **Modelos**: dataclasses con `from_dict()` como `classmethod`, campos con
   defaults inmutables y `field(default_factory=...)` para listas y modelos
   anidados.
2. **Doble metodo**: todo metodo tipado tiene su gemelo `_raw()` con la misma
   firma, que devuelve el `dict` o `list[dict]` del campo `data`.
3. **Docstrings en espanol**, sin acentos, con `Args:` y `Returns:` donde
   aplique. Los nombres de metodos y argumentos van en ingles.
4. **Tipado**: type hints en todos los parametros y retornos; `str | None` en
   lugar de `Optional[str]`.
5. **Constantes**: los valores de protocolo (mercados, plazos, paises, canales)
   viven en `constants.py` y se exportan desde `pyIol2`; no los repitas como
   literales.
6. **Validacion local**: las request de escritura validan el contrato antes de
   salir (`_order_body`, `_repo_body`, `_redemption_body`) y fallan con
   `IOLValidationError`.
7. **Sin reintentos ciegos**: el unico reintento automatico es una
   reautenticacion ante un `401`, porque esa request no llego a ejecutarse.

### Agregar un endpoint

```python
# 1. models.py: el modelo y su from_dict()
@dataclass
class NuevoModelo:
    """Descripcion del recurso."""

    campo: str = ""
    valor: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NuevoModelo":
        return cls(
            campo=data.get("campo", ""),
            valor=_to_float(data.get("valor")),
        )

# 2. client.py: version tipada y version raw, en ese orden
def get_nuevo(self, symbol: str, market: str = DEFAULT_MARKET) -> NuevoModelo:
    """Descripcion del endpoint."""
    return NuevoModelo.from_dict(self.get_nuevo_raw(symbol, market))

def get_nuevo_raw(self, symbol: str, market: str = DEFAULT_MARKET) -> dict[str, Any]:
    """Version JSON de `get_nuevo`."""
    return self._get_data("GET", f"/broker/nuevo/{symbol}", params={"market": market}) or {}

# 3. __init__.py: exportar el modelo
# 4. tests/fixtures: agregar el payload
# 5. doc/api-reference.md: agregar la seccion
```

Si el endpoint escribe (crea, cancela, suscribe), ademas:

- Acepta `idempotency_key: str | None = None` y usa
  `self._idempotency_headers(idempotency_key)`.
- Documenta el efecto en el docstring ("Mueve dinero real").
- Agrega el test que prueba que un cuerpo invalido falla antes de la request.

## Tests

- Framework: `pytest` con `pytest-asyncio` en modo `auto` (los `async def` no
  necesitan decorador).
- Ubicacion: `tests/`, un archivo por modulo (`test_auth.py`, `test_client.py`,
  `test_constants.py`, `test_models.py`, `test_stream.py`).
- Los payloads de fixture viven en `tests/` y reproducen el sobre
  `{meta, data, error}` de la v1.
- **Los tests nunca llaman a la API real.** No hay red: el cliente HTTP se
  reemplaza con `httpx.MockTransport` y el WebSocket con un `connect_factory`
  falso.
- **Los tests nunca contienen credenciales reales.** Usa valores de mentira
  (`"usuario"`, `"password"`, tokens `"jwt-1"`).
- Todo bug se arregla agregando primero el test que lo reproduce.

## Commits

Conventional Commits, en ingles, en imperativo y con alcance opcional:

```text
feat: add watchlist rename
fix(stream): keep the heartbeat alive after reconnect
docs: document the raw method contract
test: cover repo limit validation
chore: bump ruff
refactor(client): extract the order body builder
```

Tipos habituales: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.
El mensaje describe el cambio, no el archivo tocado. Un commit por cambio
logico; no mezcles formato con funcionalidad.

## Flujo de Ramas

```bash
# 1. Rama nueva desde main
git checkout -b feature/watchlist-rename

# 2. Cambios + tests + docs
uv run ruff check pyIol2/ tests/
uv run ruff format pyIol2/ tests/
uv run pytest tests/ -q

# 3. Commit
git add .
git commit -m "feat: add watchlist rename"

# 4. Push y Pull Request
git push origin feature/watchlist-rename
```

- `main` siempre queda verde: el CI corre ruff, el chequeo de formato y la suite
  de tests antes de publicar.
- Los Pull Request necesitan tests para cambios de comportamiento y actualizar
  `doc/api-reference.md` cuando cambia la superficie publica.
- No commitees `dist/`, `.env`, `.venv/`, caches ni notebooks ejecutados con
  datos de una cuenta real.

## Versionado y Releases

El paquete sigue [Semantic Versioning](https://semver.org/). Mientras la
version sea `0.x`, un cambio incompatible sube `MINOR` y uno compatible sube
`PATCH`.

La version vive en dos lugares y tiene que coincidir en los dos:

- `pyproject.toml` → `[project] version`.
- `pyIol2/__init__.py` → `__version__`.

El release se dispara con un tag `vX.Y.Z`, publica primero en TestPyPI y
despues en PyPI si la version no es prerelease. El paso a paso esta en
[`RELEASE_CHECKLIST.md`](./RELEASE_CHECKLIST.md); no publiques a mano.

## Documentacion

| Archivo | Que documenta |
|---------|---------------|
| `README.md` | Presentacion, instalacion, ejemplo REST y streaming, migracion |
| `doc/README.md` | Indice de la documentacion |
| `doc/agent-guide.md` | Guia para agentes de IA |
| `doc/api-reference.md` | Referencia de la superficie publica |
| `doc/recipes/*.py` | Recetas cortas, de solo lectura |
| `doc/notebooks/*.ipynb` | Notebooks paso a paso, sin ejecutar |
| `llms.txt` | Mapa del repositorio para agentes |

Reglas para la documentacion:

- Los nombres, defaults y tipos tienen que existir tal como estan en el codigo.
  Si tocas una firma, actualizas `doc/api-reference.md` en el mismo commit.
- Un metodo por seccion, en el orden en que aparece en `client.py`.
- Las recetas leen credenciales de `os.environ`, tienen
  `if __name__ == "__main__":` y no escriben en la cuenta (la unica excepcion es
  la estimacion, que no tiene efectos).
- Los notebooks se commitean sin ejecutar: `execution_count: null` y
  `outputs: []`.

---

## Preguntas Frecuentes

### El test de streaming se cuelga

`IOLStreamClient.subscribe()` es un generador asincronico: si el test no corta
la iteracion, el `async for` espera mensajes para siempre. Usa un conteo maximo
y `break`, o un `connect_factory` que cierre la conexion.

### `uv run ruff format --check` falla en el CI pero localmente no

El CI corre sobre todas las versiones de Python soportadas y con la version de
ruff fijada en `uv.lock`. Corré `uv sync --all-extras` antes de validar.

### Faltan credenciales para probar a mano

Las recetas de `doc/recipes/` son el camino corto: exporta `IOL_USERNAME` e
`IOL_PASSWORD` y ejecutalas con `uv run python doc/recipes/quote.py`. No agregues
credenciales a ningun archivo del repositorio.
