# pyIol2 v0.1.0 — new client for the IOL Inversiones API v1

New repository at `D:/MisProyectos/iol/pyIol2`, sibling of the legacy `py_iol`
project, targeting the new IOL platform (`api.iolinversiones.com` + market-data
WebSocket). It mirrors the legacy project's philosophy and conventions:
typed dataclasses with `from_dict()`, a `_raw()` twin for every typed method,
Spanish docstrings, ruff + pytest, uv as the package manager, and docs written
both for humans and for AI agents.

## Specs

S1. New standalone project, not a change to `py_iol`:
> "creemos un proyecto nuevo en la subcarpeta padre iol que se va a llamar pyIol2"

S2. Same purpose as the legacy library, against the new API, covering its new
   capabilities:
> "la idea es la misma que py_iol, una librería de python para abstraer la implementación del cliente de la api de iol en este caso al nueva, incorporando todos los elementos nuevos"

S3. Same philosophy and conventions, including contribution docs, code style,
   documentation, agent-oriented documentation and notebooks for developers:
> "siguiendo la misma filosofia y convesiones del proyecto py_iol , contribuciones, estilo de programación, documentación, documentacion para el agente, notebooks para los programadores, etc."

S4. `uv` as package manager, tests, ruff, and a brand new git repository:
> "el proyecto utiliza uv como gestor de paquetes tiene test, ruff, pero todo e un nuevo repo"

S5. Publish the repository under the owner's GitHub account as **private** first,
   iterate, then release later:
> "despues lo pusheamos en mi user como privado hasta que lo iteremos algunas veces luego lo liberamos"

S6. CI must be configured, plus the pip installation repositories to publish
   packages to test and production:
> "tambien hy que configurar el ci del proyecto y los repotos de pip install para publicar los paquetes en test y prod"

S7. The legacy API is expected to be retired, although IOL has not announced it:
> "posiblemente la maten a la api vieja aunque no dijeron nada"

## Tasks

| ID | Spec | Route | Deliverable |
|----|------|-------|-------------|
| T1 | S1, S4 | inline | Repo skeleton: `git init`, `pyproject.toml` (uv/hatchling), `.gitignore`, licence, package tree |
| T2 | S2 | inline | `constants.py` (hosts, `Markets`, `SettlementTerms`, channels) and `exceptions.py` (typed error with `trace_id`) |
| T3 | S2 | inline | `auth.py`: OAuth2 password grant + `refresh_token` renewal behind a TTL cache |
| T4 | S2 | inline | `models.py`: dataclasses for the full v1 surface, each with `from_dict()` |
| T5 | S2 | inline | `client.py`: sync `IOLClient` with typed + `_raw()` methods for every endpoint |
| T6 | S2 | inline | `stream.py`: async `IOLStreamClient` (auth, subscribe, heartbeat, reconnect, sharding) |
| T7 | S4 | inline | `tests/`: fixture payloads + `MockTransport`-based suite for models, client, auth and stream |
| T8 | S6 | inline | `.github/workflows/`: `ci.yml`, `security.yml`, `publish.yml` (TestPyPI then PyPI), `scripts/validate_version.py`, `renovate.json` |
| T9 | S3 | delegated | Human docs: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`, `RELEASE_CHECKLIST.md`, `llms.txt` |
| T10 | S3 | delegated | Agent + developer docs: `doc/agent-guide.md`, `doc/api-reference.md`, `doc/recipes/*.py`, `doc/notebooks/*.ipynb` |
| T11 | S5 | inline | First commit, private GitHub repo, push |

## Log

L1 (verbatim, original request):
> iol acaba de sacar una nueva api mas moderna incorpoa web sockets ? que conviene hacer una nueva librería o hacer un major version de este proyecto?

L2 (verbatim):
> posiblemente la maten a la api vieja aunque no dijeron nada

L3 (verbatim):
> hagamos una cosa creemos un proyecto nuevo en la subcarpeta padre iol que se va a llamar pyIol2, la idea es la misma que py_iol, una librería de python para abstraer la implementación del cliente de la api de iol en este caso al nueva, incorporando todos los elementos nuevos, pero siguiendo la misma filosofia y convesiones del proyecto py_iol , contribuciones, estilo de programación, documentación, documentacion para el agente, notebooks para los programadores, etc. el proyecto utiliza uv como gestor de paquetes tiene test, ruff, pero todo e un nuevo repo y despues lo pusheamos en mi user como privado hasta que lo iteremos algunas veces luego lo liberamos, tambien hy que configurar el ci del proyecto y los repotos de pip install para publicar los paquetes en test y prod

L4 (decision, parent): separate distribution rather than a `1.0.0` of `py_iol`,
because neither API is a superset of the other: v1 has no MEP/CPD/advisor
endpoints, v2 has no historical bars, depth, screener, watchlists or streaming.
A major bump would tax every existing `pyiol-client` user to add a different
product, and the WebSocket runtime (async, long-lived) does not fit the sync
`httpx` client cleanly.

L5 (decision, parent): Python floor is `>=3.10` (legacy project is `>=3.8`).
The async streaming stack and modern typing justify it, and separate
distributions keep each floor independent.

L6 (evidence): the v1 contract was frozen from the vendor OpenAPI rendering
(`OpenAPI 3.1.2`, `API Version 1.0.0`) and the WebSocket docs page; the
committed snapshot lives in `doc/vendor/iol-api-v1.md`. Base URLs:
`https://api.iolinversiones.com` (REST) and
`wss://stream-marketdata.invertironline.com` (market data only).

L7 (decision, parent): the package module keeps the user's naming (`pyIol2`)
and the distribution is `pyiol2-client`, mirroring the legacy
`pyiol-client` distribution that publishes `pyIol`.

L8 (open): no deprecation date for the legacy API is public. The new library
therefore ships no v2 compatibility shim; migration guidance lives in the
README instead.

L9 (evidence, T1-T7): `uv sync --all-extras` resolves on Python 3.10+ with
httpx 0.28, cachetools 5.5 and websockets 17.4. Package layout: `constants.py`,
`exceptions.py`, `auth.py`, `models.py`, `client.py`, `stream.py`, `__init__.py`.
`uv run ruff check` and `ruff format --check` are clean; `uv run pytest tests/ -q`
is green with 92 tests and 94% statement coverage (models 99%, client 88%,
stream 87%, auth 93%).

L10 (decision, parent): the sync REST client keeps the legacy philosophy
(dataclasses with `from_dict()`, typed method plus `_raw()` twin, Spanish
docstrings) and adds local contract validation before any write, so an invalid
order never reaches the API: `quantity` XOR `notional`, `limit_price` required
for limit orders, `rate` required for limit repos, and quantity XOR `redeem_all`
for FCI redemptions.

L11 (decision, parent): idempotency keys are generated client-side (uuid4) when
the caller does not supply one, because `POST /broker/orders`, `/broker/repos`
and the FCI write endpoints require the `X-Idempotency-Key` header.

L12 (decision, parent): the only automatic retry is a single re-authentication
on 401, since that status means the request was rejected before execution and
cannot duplicate a write. 5xx and 429 are surfaced to the caller instead of
being retried blindly.

L13 (decision, parent): the streaming client shards >50 symbols across
connections, keeps the heartbeat task alive because the server never pings, and
re-raises connection errors into the consumer queue so a dead socket cannot
leave an `async for` hanging forever.

L14 (blocker, environment): the harness safety policy blocks creating
`.env.example` in this session, so the README documents the two environment
variables instead of pointing at a copyable example file. The maintainer can add
the file by hand if the conventional layout is wanted.

L15 (evidence, T8): worker `mwqe6fby-2-0tng` delivered `ci.yml`, `security.yml`,
`publish.yml`, `scripts/validate_version.py`, `renovate.json` and the GitHub
templates. Verified independently: the three workflows parse as YAML and
`scripts/validate_version.py v0.1.0` exits 0 with the production path. Neither
workflow has run on GitHub yet.

L16 (evidence, T9/T10): worker `mwqe6fc6-3-u9ga` delivered README, CONTRIBUTING,
SECURITY, CHANGELOG, RELEASE_CHECKLIST, llms.txt, `doc/README.md`,
`doc/agent-guide.md`, `doc/api-reference.md`, 5 recipes and 4 nbformat-4
notebooks. Verified: recipes pass ruff and `ast.parse`, notebooks pass
`nbformat.validate` with `execution_count` null and `outputs` empty.

L17 (fix, from L16 contradictions): `IOLConnectionError` was exported but never
raised; `client.py` and `auth.py` now raise it on `httpx.HTTPError` and a test
covers it. `StreamActions.UNSUBSCRIBE/UNSUBSCRIBE_ALL` had no public method, so
`IOLStreamClient.unsubscribe()` and `unsubscribe_all()` now exist, with their
own control-frame pump per connection. The tests caught a real aliasing bug:
`quotes` and `trades` shared the same list instance, so unsubscribing from one
channel emptied the other.

L18 (evidence, real API): ran `scripts/smoke_test.py --with-stream` against
production with the maintainer's credentials, read-only, market closed:
17 of 18 steps OK. Confirmed live: `/health`, OAuth2 login and
`test_authentication`, quote, depth (empty lists when closed), asset, 12 asset
types, screener (99 rows), option chain (128 contracts), historical bars,
repo terms, balances, 32 positions, activities, trading operations, watchlists
(1 with 26 items) and the WebSocket handshake with `auth_token` + `subscribe`.

Deviations found against the published contract, all now documented in
`doc/agent-guide.md` under "Lo Que Devuelve la API Real":

- `asset_type` ids are Spanish (`acciones`, `cedears`, ...); there is no
  `stocks`. `panel` ids look like `argaccionespanelgeneral`.
- `term=T0` on GGAL returns `settlement_term: "T1"`: the API normalises to the
  term the asset trades on.
- `/broker/accounts/{country}/portfolio/history` answers 404
  `{"error": "client_not_whitelisted", "clientId": ...}` for a non-whitelisted
  account, with `error` as a plain string instead of the documented object.
- The WebSocket confirms a subscription with `{"type": "Success"}`, a message
  type absent from the published contract; it surfaces as a `StreamMessage`
  with empty `symbol`/`term` and the raw JSON.
- `repos/quotes` returns `[]` for every term while the market is closed, so the
  `term_id` mapping between `/repos/terms` and `/repos/quotes` remains
  unverified and needs a retest during trading hours (open question, L19).

L19 (open): retest `get_repo_quotes()` and the write paths (`/broker/orders`
estimate, FCI validate) during trading hours before releasing.

L20 (evidence, real writes): ran `scripts/order_roundtrip.py --yes` four times
against production with the market closed. Buy path validated end to end on
COME: `create_order` accepted (order ids 196806748, 196806749, 196806752),
`get_trading_operations` showed each order with `status: "pending"` within
seconds, and `cancel_order` returned `cancelled: True` / `status: "cancelled"`.
No order was left alive; the script cancels in `finally` and exits non-zero if
anything survives.

Findings that changed the code: the order body must always carry
`settlement_term` (the API answers 400 without it, although the contract marks
it optional), so `_order_body` now defaults to `T1` and
`DEFAULT_SETTLEMENT_TERM` moved from `T0` to `T1` to match how the API actually
prices assets.

Findings that remain open: sell orders were rejected with an opaque
`422 ORDER_REJECTED` for a held CEDEAR (JNJ), a held local instrument (PAMP) and
a non-held symbol (KO), and `details` was empty in every case. Market orders are
rejected outside trading hours, and a PAMP buy at 4316 with 3064 ARS available
was rejected with the same code, so available balance has to be checked before
sending a real order. The accepted-sell path is still unverified (L21).

L21 (open): retest the sell path during trading hours and find out whether the
rejection is a pre-condition of the closed market or something about the
account's sell permissions.

L22 (fix, from the native review findings): the escalated review's findings were
real. Corrections applied in a separate work unit:

- R3-001 / R4-001: changing the shared `DEFAULT_SETTLEMENT_TERM` from `T0` to
  `T1` also moved the WebSocket subscription default, an unrequested feed change
  for stream consumers. Market data keeps `T0`; orders now use their own
  `DEFAULT_ORDER_SETTLEMENT_TERM = T1`.
- R1-SETTLEMENT-FALSY (refuted, still a wart): `settlement_term or default`
  replaced an explicitly empty value; now only `None` falls back.
- R1-ORDER-UNCERTAIN / R3-002 / R4-003: the round-trip script registered an
  order id only after logging, so a broken stdout or a parsing failure after the
  broker accepted could leave a live order uncancelled. The id is now recorded
  immediately, printing can never raise, and an ambiguous `create_order` is
  reconciled against the day's operations instead of being retried.
- R4-002: cancellation now removes the id from the alive list before printing.
- R1-ORDER-ROUNDING (refuted, still a wart): limits are computed so they never
  equal the reference price, and the script aborts before sending anything if
  the cushion is not real.
- R3-003: verification failures now affect the exit status.

Re-verified against production after the corrections: buy COME accepted
(196806828), verified as `pending`, cancelled (`cancelled=True`), no live orders;
the sell is still rejected with the opaque `ORDER_REJECTED` (open, L21).
