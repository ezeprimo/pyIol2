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

L23 (evidence, native review verdict on the correction): the targeted validator
rejected the correction and its evidence was correct on all three points:

- `_open_orders` still caught `IOLAPIError` and returned `[]`; the replacement
  silently did not apply, so the guarded `_reconcile` call could never receive a
  lookup failure.
- the reconciliation still ignored the order side.
- changing `settlement_term=""` into a local validation error was an
  out-of-scope, backward-incompatible behaviour change.

Fixed afterwards as ordinary work, not as a review correction: `_open_orders`
propagates, the reconciliation matches side and term against the pre-run
baseline of live ids, and empty `settlement_term` passes through as before
(only `None` falls back to the order default). 104 tests green.

L24 (terminal): lineage `review-2d1cdc67c3790ae8` ended `escalated` /
`native_stop_required` with `targeted_validator_rejected`; its single bounded
correction was consumed and failed, so no further correction or continuation is
offered for that candidate. A fresh review of the new commit would be a new
transaction and needs a human decision, as does delivery.

L25 (evidence, sell path resolved): the earlier sell rejections were a price
problem, not holdings or tickers. KO is held (24 available) and is a valid BCBA
CEDEAR; PAMP (31) and JNJ (5) were also available. Probed the band with KO
(last 34,820) and cancelling each acceptance immediately: `0.95x`, `0.99x` and
`1.05x` were rejected with `422 ORDER_REJECTED`; `1.00x` and the `market` sell
were accepted. So the accept band is not symmetric: buys take 0.95x, sells only
the reference price.

Corrections that followed: `scripts/order_roundtrip.py` sells at the reference
price and refuses to run when the cushion is not real on the buy side;
`_find_order` retries with a bounded wait because the operations feed lags a few
seconds behind order creation. Full round-trip verified against production:
buy COME (196807038) and sell KO (196807039) both `pending`, both
`cancelled=True`, no live orders, exit 0.

L26 (fix, correction of review-19cff5531a4b60a3): the reviewers caught two real
defects and one broken promise of mine.

- R3-001 (BLOCKER, deterministic): the `_reconcile` call site still passed seven
  positional arguments to an eight-parameter function, so any ambiguous
  `create_order` raised `TypeError` instead of reconciling. Same class of
  failure as L23: a textual replacement that did not apply. Edits now assert
  that the old text exists before replacing it.
- R1-002 / R3-002 / R4-SELL-REFERENCE-EXECUTION: selling at the reference price
  is marketable, so my "no execution risk" guarantee no longer held, and
  verification ran before cancellation, keeping the order live for up to ten
  seconds. The sell leg is passive again by default (5% above reference, which
  the broker may reject on band) and the marketable variant is opt-in behind
  `--allow-marketable-sell`.
- Verification now runs after cancellation, so no order is live while the
  operations feed is polled, and it fails the run when an order is missing or
  left open. `_reconcile` tolerates market orders without a price.

Re-verified against production with the opt-in flag: buy COME (196807075) and
sell KO (196807076) created, cancelled, and both verified as `cancelled`
afterwards; exit 0 and no live orders.

L27 (decision, from the maintainer's follow-ups): `settlement_term=""` is now an
explicit `IOLValidationError`; `None` remains the documented way to ask for the
order default. Covered by two tests (order and estimate).

L28 (evidence): the operations feed has 13 fields and none of them echoes the
`X-Idempotency-Key` we send, so a request cannot be correlated with an order
after an ambiguous create. The round-trip script therefore also matches on
`order_date` within a bounded window around the request, on top of the pre-run
baseline and the attribute match. Verified the call/signature arity
programmatically (9 = 9) instead of trusting the edit.

L29 (follow-ups closed from review-adee67cec88d0ab2, all advisory): the three
findings pointed at the same hole in `_within_window`. A timezone-aware
`order_date` produced an aware datetime and the subtraction against a naive
`datetime.now()` raised `TypeError` outside the handler, aborting the
reconciliation of an ambiguous create. Offsets are now normalised to local naive
time and every unparseable value returns False. The helper also got its own test
module (`tests/test_order_roundtrip_script.py`), loading the script by path so
the window boundary, the offset case and the unparseable inputs are covered.

L30 (follow-ups closed from review-9b629a8ae9f36ed9): the offset test asserted
only "does not raise" with a different instant, which a broken implementation
returning False for every aware input would pass; it now asserts the same
instant with offset is accepted and an out-of-window offset is rejected. The
`str(order_date)` coercion also widened the accepted domain, so the helper is
strict again and rejects non-string input, with a test for it. 112 tests.

L31 (evidence, S6 complete): the release pipeline ran for real. `publish.yml`
dispatched with `target=testpypi` (run 45088549838) and all three real jobs
passed: Validate version, Release checks (ruff + pytest + build + twine check)
and Publish to TestPyPI; Publish to PyPI was skipped because the version is a
prerelease, exactly as designed. Sigstore attestations were generated.

Verified afterwards: `https://test.pypi.org/simple/pyiol2-client/` returns 200
(it was 404 before the first publish, which is how the pending publisher was
confirmed), the only release is `0.1.0b1` with the wheel and the sdist, and a
clean-venv install from TestPyPI (`--extra-index-url` to PyPI for the
dependencies) imports and works: `pyIol2.__version__`, `Markets`,
`SettlementTerms`, `build_symbol_id`, lazy token.

Known wart found here: `__version__` and `pyproject.toml` both carry the raw
`0.1.0-beta.1` while the distribution normalises to `0.1.0b1`, so the module
string and the metadata disagree. Normalising both would break the prerelease
detection in `publish.yml`, which matches the dashed spelling, so the fix is to
normalise the module string only and make the CI comparison tolerant of PEP 440
normalisation. Left as a follow-up so as not to re-release a different artifact.

L32 (defect, external): the gentle-pi RDD delivery preflight
(`lib/review-delivery-preflight.ts:45`) bounds the whole preflight with
`AbortSignal.timeout(10_000)`, and inside that budget it spawns three
`gentle-ai` calls (`review mode status`, `review status`, `review assess`) plus
`git rev-parse`. Measured on this machine: the raw CLI takes 0.2s / 0.14s / 1.8s
(2.2s total), but the Pi adapter path for `assess` measured 7.9-10.9s across four
calls in this session, so the sequence straddles the 10s bound and delivery was
denied intermittently with "The bounded preflight was cancelled or timed out".
`git push --dry-run` was allowed only because a dry run is not classified as a
delivery, which also means it proves nothing about the gate. Workaround used: the
maintainer ran `git push` locally. Proposed upstream fix: skip the native
untracked-inventory lookup when `git status --porcelain --untracked-files=normal`
is empty, and give the aborted-signal and timeout cases distinct messages.

L33 (evidence, market open): re-ran the probes with the rueda operando.
WebSocket now shows the real flow: in seconds, `9 Q` + `2 T` for GGAL and YPFD,
prices matching the REST quote (GGAL 4405, -4.44%), trades carrying cumulative
day totals plus the per-trade quantity, and the `order_book` channel delivering
10 levels whose level-5 size changed between messages (so it is live, not a
snapshot). REST `depth` returned 5+5 levels where it returned empty while closed.

L34 (resolved, was L19/L21): cauciones work with the market open. 81 terms, and
12 of 12 sampled terms returned 5 offers each with bid/ask rates. The earlier
`[]` was the closed market, not a broken `term_id` mapping.

L35 (fix, from L33): the `Success` frame arrived as a `StreamMessage` with no
symbol, forcing every consumer to filter it. `STREAM_PROTOCOL_TYPES` now drops
`Success` and `Pong` inside the connection, so `subscribe()` only yields market
data and a rejected subscription still surfaces as `IOLStreamError`. Test added;
113 tests green.

L36 (safety, from the maintainer's warning): `scripts/order_roundtrip.py` now
refuses to run when the quote was refreshed within 15 minutes (market likely
open), and also refuses when freshness cannot be determined, unless
`--allow-open-market` is passed. Verified read-only: quote age 3s, market open,
guard aborts without the flag. The script was NOT executed with `--yes` at any
point while the market was open.

L37 (evidence, block 1 of the pending list): ran `scripts/safe_write_probe.py`
against production with the market open. Three of three groups passed, with no
residue in the account.

- Watchlists CRUD end to end: created id 247707, renamed, added GGAL, read it back
  with a live quote (bid 4575, ask 4602.5), removed it, deleted the list. The
  account went from `[74964]` before to `[74964]` after: the real watchlist with
  26 items was never touched.
- `estimate_order`: market buy of 1 GGAL returned `importe=4602.5`, which was the
  `best_ask` and not the last price, so the estimate is conservative. Commission
  came out at ~0.5% of the amount (23.01 on 4602.5; 25 on 5000) plus VAT and a
  separate market fee. A limit estimate at 4556.48 priced the order at the limit.
- `estimate_repo`: terms carry a real `min_amount` (100,000 ARS), and each term
  returns **several components, not one total** — two rows in the sample: the
  period interest and the commission plus its VAT (21% of the commission,
  `commission_type` = Porcentaje). Documented so nobody sums the list as if it
  were a single fee.

Still unverified and deliberately so (they move money): `create_repo`,
`cancel_repo`, `subscribe_fund`, `redeem_fund`, `cancel_fund_operation`.

L38 (evidence, block 2): ran `scripts/stream_stress_probe.py` against the live
server with the market open. Four of four scenarios passed.

1. Sharding: 60 symbols produced 2 connections with `[50, 10]` symbols and data
   arrived on both, so the 50-per-channel cap and the automatic split hold against
   the real server.
2. `unsubscribe`: returns `['YPFD|BCBA|T0']` and only GGAL messages arrive
   afterwards (8 of them), so the frame the library builds is what the server
   expects.
3. `unsubscribe_all`: zero messages in an 8 second window with the socket open.
4. Reconnection: an injected drop on the first connection produced the library's
   own `reintento 1/5 en 1.0s`, a fresh connection, re-authentication, automatic
   re-subscription and 4 more messages.

The one failure along the way was in the probe, not the library: `websockets` 17
implements `ClientConnection.__aiter__` as a coroutine and exposes no `__anext__`,
so a wrapper must delegate with its own async generator. Documented in the agent
guide because anyone writing a custom connect factory will hit it.

With this, the streaming surface is verified end to end against production.
Still unverified and deliberately so, because they move money: `create_repo`,
`cancel_repo`, `subscribe_fund`, `redeem_fund`, `cancel_fund_operation`.

L39 (docs): added `scripts/README.md` as the catalogue of the verification tools,
because the scripts had grown to six with very different risk profiles and nothing
told them apart. Each tool documents its purpose, flags, requirements, expected
output and gotchas; the summary table carries an explicit "moves money" column so
the one script that can place a real order cannot be confused with the five that
cannot. Linked from `README.md`, `doc/README.md`, `llms.txt` and `CONTRIBUTING.md`.
Core reviewed with L38's findings fixed in it.

L40 (debt, the two items that were open):

- The offset test was host-dependent: it built the aware timestamp with
  `sent_at.astimezone()`, so on a UTC host it only covered `+00:00` and an
  implementation that dropped `tzinfo` instead of normalising it would still have
  passed. It now uses a fixed non-local offset (UTC-5) and asserts against the
  correctly converted local time. Verified the test is sensitive: the real helper
  returns True for that pair while a deliberately buggy version that drops the
  offset returns False.
- `bars[].datetime` was documented only in passing. The API returns two shapes
  for the same field depending on the moment (`"2026-01-01 10:00:00"` without a
  zone, and `"2026-11-25T15:40:10.000Z"`), so the model docstring, the API
  reference and the agent guide now say so and point at `bars[].timestamp` (unix
  seconds) for ordering or filtering.

Still blocked by the environment, not by us: `.env.example` cannot be created
because the harness safety policy refuses every `.env*` path. The README
documents the two variables instead.

L41 (evidence, money block as far as it can go without moving money): ran
`scripts/money_write_probe.py` with the market closed and 3,064.88 ARS available.

- `estimate_repo`: the components carry real names — `fee_type` "Derechos de
  Mercado" (0.50) and "Comision" (4.93) per term, each with its 21% VAT.
- `create_repo` with the 100,000 ARS minimum answered **500 INTERNAL_ERROR**, not
  a friendly 422: no order id came back, so nothing was created. The accepted
  repo path is unreachable with this balance and needs no decision.
- `cancel_repo("0")` returns 422 with a body that is not the standard envelope
  (`{"success":false,"message":"Transaction was not found.",...}`) plus a
  `Service https://activities.invertironline.com/...` string, so the cancel is
  proxied to the legacy activity service.
- FCI: `validate_fund_subscription("IOLCAMA", 1000)` = `valid=True`, and
  `validate_fund_redemption` without holdings gives `FCI-23` "No se encontró el
  título para el cliente". v1 has no fund catalogue, so the symbol must come from
  outside.

Remaining and deliberately not executed: a real FCI subscription (moves money
into a fund, cancellation window unknown). It is the only money write that is
actually reachable with this balance, so it needs an explicit decision.
