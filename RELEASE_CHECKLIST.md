# Release Checklist

Checklist de release de `pyiol2-client`. Ordena el trabajo del mantenedor: no
publica nada por si solo. La publicacion la ejecuta el workflow
`.github/workflows/publish.yml` cuando se pushea un tag `v*`.

## Camino Corto

1. Subir la version en los dos archivos que la declaran.
2. Actualizar `CHANGELOG.md`.
3. Correr ruff y los tests.
4. Construir y validar las distribuciones.
5. Commitear, crear `vX.Y.Z` y pushear el tag.
6. Verificar la publicacion en TestPyPI y la instalacion de humo.
7. Para versiones no prerelease, confirmar la publicacion en PyPI.

## 1. Version

La version tiene que coincidir en los dos lugares:

- [ ] `pyproject.toml` → `[project] version = "X.Y.Z"`.
- [ ] `pyIol2/__init__.py` → `__version__ = "X.Y.Z"`.

Verificacion rapida:

```bash
uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
uv run python -c "import pyIol2; print(pyIol2.__version__)"
```

Cuando subir cada numero (mientras la version sea `0.x`):

| Cambio | Numero |
|--------|--------|
| Cambio incompatible en la superficie publica o en las constantes | `MINOR` |
| Funcionalidad nueva compatible | `MINOR` |
| Correccion compatible | `PATCH` |

Sufijos de prerelease: `-alpha.N`, `-beta.N`, `-rc.N`, `-dev.N`. pip normaliza
`0.2.0-beta.1` a `0.2.0b1`.

## 2. CHANGELOG

- [ ] Agregar la seccion de la version con fecha en `CHANGELOG.md`, en formato
      [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
- [ ] Agrupar los cambios en `Added`, `Changed`, `Deprecated`, `Removed`,
      `Fixed` o `Security`.
- [ ] Anotar explicitamente los cambios incompatibles y la migracion necesaria.
- [ ] Confirmar que el link de comparacion del pie apunta al release anterior.

## 3. Validacion Local

Correr desde la raiz del repositorio y con el arbol limpio:

- [ ] Lint y formato:

```bash
uv run ruff check pyIol2/ tests/
uv run ruff format --check pyIol2/ tests/
```

- [ ] Tests:

```bash
uv run pytest tests/ -q
uv run pytest tests/ -q --cov=pyIol2
```

- [ ] Confirmar que no hay credenciales ni artefactos en el cambio:

```bash
git status --short
git grep -n -I -E "(IOL_PASSWORD|IOL_USERNAME|access_token|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)" -- ':!doc/vendor' ':!*.lock'
```

## 4. Build y Verificacion de Artefactos

- [ ] Limpiar builds anteriores y construir:

```bash
rm -rf dist/
uv build
```

- [ ] Validar los metadatos de wheel y sdist:

```bash
uv run twine check dist/*
```

> `twine` no esta entre las dependencias de desarrollo, asi que el comando
> anterior solo funciona si ya esta instalado. La forma que siempre resuelve es
> `uv run --with twine twine check dist/*`, que lo trae al vuelo.

- [ ] Confirmar que la wheel solo contiene el paquete y no la documentacion:

```bash
uv run python -c "import glob,zipfile; print('\n'.join(zipfile.ZipFile(glob.glob('dist/*.whl')[0]).namelist()))"
```

El sdist excluye `doc/`, `odd/`, `.env` y `.git` (ver
`[tool.hatch.build.targets.sdist]` en `pyproject.toml`); la wheel empaqueta solo
`pyIol2`.

## 5. Commit y Tag

- [ ] Commitear el cambio de version y el CHANGELOG:

```bash
git add pyproject.toml pyIol2/__init__.py CHANGELOG.md
git commit -m "chore(release): vX.Y.Z"
```

- [ ] Confirmar que el tag y `pyproject.toml` coinciden antes de pushear (el
      workflow falla si no):

```bash
uv run python scripts/validate_version.py vX.Y.Z
```

- [ ] Crear el tag anotado, con el nombre exacto de la version:

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git show --no-patch --decorate vX.Y.Z
```

- [ ] Pushear `main` y el tag. **Este push dispara la publicacion:**

```bash
git push origin main
git push origin vX.Y.Z
```

No pushees el tag hasta que la configuracion de Trusted Publishing este hecha y
verificada (paso 7).

## 6. Que Hace `.github/workflows/publish.yml`

El workflow corre solo con tags `v*` (o a mano con `workflow_dispatch`,
  eligiendo `testpypi` o `pypi`) y encadena estos jobs:

1. **`validate`**: compara el tag con la version de `pyproject.toml`, detecta si
   es prerelease y corre `scripts/validate_version.py`.
2. **`checks`**: `uv sync --all-extras`, ruff sobre `pyIol2/ tests/ scripts/`,
   `pytest`, `uv build` y `uv run --with twine twine check dist/*`.
3. **`testpypi`**: publica siempre en TestPyPI con Trusted Publishing
   (`id-token: write`, environment `testpypi`) contra
   `https://test.pypi.org/legacy/` y `skip-existing: true`.
4. **`pypi`**: publica en PyPI solo cuando la version **no** es prerelease, con
   el environment `pypi`.

No hay tokens de larga vida: la autenticacion es OIDC.

- [ ] Confirmar que `validate` y `checks` pasaron antes de aceptar la
      publicacion en TestPyPI.
- [ ] Confirmar que el job `pypi` quedo salteado en un prerelease y se ejecuto en
      una version estable.

## 7. Configuracion Unica: Trusted Publishing

Se hace una sola vez por indice, y hay que repetirla en TestPyPI y en PyPI.

- [ ] En GitHub, crear los environments `testpypi` y `pypi` del repositorio
      (`Settings → Environments`).
- [ ] Si corresponde, agregar reglas de proteccion: reviewers requeridos y
      restriccion de tags/ramas.
- [ ] En [TestPyPI](https://test.pypi.org) → `Account settings → Publishing` →
      `Add a new pending publisher`, completar:
      - PyPI Project Name: `pyiol2-client`
      - Owner: `ezeprimo`
      - Repository name: `pyIol2`
      - Workflow name: `publish.yml`
      - Environment name: `testpypi`
- [ ] Repetir en [PyPI](https://pypi.org) con environment `pypi`.
- [ ] Verificar los cuatro datos directamente en GitHub y en el indice; no
      inferirlos de este documento.

El primer release deja el publisher en estado pendiente; queda activo cuando la
publicacion crea el proyecto.

## 8. Instalacion de Humo desde TestPyPI

En un entorno nuevo, fuera del repositorio:

```bash
python -m venv .release-testpypi
# Linux / macOS
. .release-testpypi/bin/activate
# Windows PowerShell
# .\.release-testpypi\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install --index-url https://test.pypi.org/simple/ pyiol2-client
```

Si TestPyPI no tiene todas las dependencias (`httpx`, `cachetools`,
`websockets`), agregar el indice de PyPI:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ pyiol2-client==X.Y.Z
```

- [ ] Confirmar la version instalada:

```bash
python -c "import pyIol2; print(pyIol2.__version__)"
```

- [ ] Si hay credenciales de una cuenta de prueba autorizada, correr una lectura:
      `python doc/recipes/quote.py`. **No ejecutes ordenes ni operaciones de
      FCI o cauciones durante el smoke test.**
- [ ] Borrar el entorno temporal al terminar.

## 9. Verificacion en PyPI

Solo para versiones no prerelease:

- [ ] Confirmar que la version no exista ya en PyPI: las versiones publicadas son
      inmutables y no se pueden sobrescribir.
- [ ] Aprobar el environment `pypi` si tiene reviewers requeridos.
- [ ] Confirmar el job de publicacion y la pagina del proyecto en PyPI.
- [ ] Instalar desde PyPI en un entorno limpio:

```bash
python -m pip install pyiol2-client==X.Y.Z
python -c "import pyIol2; print(pyIol2.__version__)"
```

## 10. Rollback y Seguimiento

- [ ] Si la validacion fallo antes de publicar, borrar solo el tag local:
      `git tag -d vX.Y.Z`.
- [ ] Si el tag ya se pusheo y hay que frenar la publicacion, deshabilitar o
      proteger los environments y documentar el motivo; no borrar artefactos ya
      publicados.
- [ ] Si aparece un problema despues de publicar, sacar una version superior. No
      se puede reemplazar un release existente.
- [ ] Registrar URLs del workflow, URLs del paquete, hashes, comandos de
      verificacion, fallas y aprobaciones, sin credenciales ni datos personales.
- [ ] Cerrar el issue de release solo despues de verificar la instalacion.

## Acciones Manuales

Estas acciones son del mantenedor y no las hace el workflow:

- Configurar los environments `testpypi` y `pypi`.
- Configurar los Trusted Publishers en TestPyPI y PyPI.
- Commitear el bump de version y crear el tag.
- Pushear el tag.
- Aprobar los environments protegidos.
- Verificar la instalacion y decidir el rollback.
