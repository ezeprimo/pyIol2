# Security Policy

## Supported Versions

Security fixes are considered for the latest published version of
`pyiol2-client`. Older versions may not receive fixes; upgrade before reporting
or evaluating an issue.

| Version | Supported |
|---------|-----------|
| `0.1.x` | Yes (latest release only) |
| `0.x` anteriores | No |

The package is in the `0.x` phase: the API v1 of IOL is new and the public
surface can change between minor versions. Check `CHANGELOG.md` before
upgrading.

## Reporting a Vulnerability

Please report suspected vulnerabilities privately. Do not open a public issue,
pull request, discussion, or forum post containing exploitable details.

Use GitHub's private vulnerability reporting feature from the repository
Security tab when it is available. If private reporting is not enabled, contact
the repository maintainers through the private channel configured here:

> **Security contact: [TO BE CONFIGURED BY REPOSITORY MAINTAINERS]**

Do not send credentials or other secrets in a report. Redact tokens, passwords,
API keys, account identifiers, personal data, and any request or response
fields that contain them.

## Information to Include

- A short description of the vulnerability and its potential impact.
- The affected `pyiol2-client` version, Python version, and operating system.
- The relevant endpoint, client method, or configuration area.
- Minimal reproduction steps or a proof of concept that does not use real
  credentials or funds.
- Expected behavior and actual behavior.
- Any logs, tracebacks, HTTP status codes, `trace_id` values, or sanitized
  request/response excerpts.
- Your preferred contact details for follow-up, if the private reporting
  channel does not provide them.

## Scope

This policy covers security issues in the `pyiol2-client` package, including
authentication, credential handling, request construction, response handling,
streaming session lifecycle, and documentation that could cause unsafe use of
the library.

The following are generally outside the project's control and should not be
reported as vulnerabilities in this repository:

- Vulnerabilities in the IOL service or its infrastructure.
- Vulnerabilities in Python, `httpx`, `cachetools`, `websockets`, or other
  third-party dependencies without a demonstrated impact through this package.
- Issues requiring access to credentials or systems that the reporter is not
  authorized to use.
- Denial-of-service testing, automated high-volume requests, or testing against
  production accounts.

Do not perform testing that could execute trades, alter account data, or disrupt
the IOL service. Use a controlled environment and authorized test accounts only.

## Credential Handling

- Pass credentials only through environment variables (`IOL_USERNAME`,
  `IOL_PASSWORD`) or a secret manager. Never hardcode them in source, notebooks,
  prompts, fixtures, logs, or command history.
- The library obtains the OAuth token from `/auth/token` and caches it in
  memory for the lifetime informed by the API; it never writes the token to
  disk.
- Never log `IOLToken.access_token` or the `Authorization` header. Log the
  request path and the `trace_id` instead.
- If a token or password is exposed, rotate the IOL password: the refresh token
  is issued from it and there is no separate revocation API in the library.

## Money-Moving Methods

Some methods execute real operations against a real account and cannot be
undone from the library:

- `create_order()` and `create_order_raw()` — submits a buy or sell order.
- `cancel_order()` and `cancel_order_raw()` — cancels a live order.
- `create_repo()` and `create_repo_raw()` — takes a caución (repo).
- `cancel_repo()` and `cancel_repo_raw()` — cancels a taken repo.
- `subscribe_fund()` and `subscribe_fund_raw()` — subscribes to a mutual fund.
- `redeem_fund()` and `redeem_fund_raw()` — redeems units of a mutual fund.
- `cancel_fund_operation()` and `cancel_fund_operation_raw()` — cancels a
  pending fund subscription or redemption.

`estimate_order()`, `estimate_repo()`, `validate_fund_subscription()` and
`validate_fund_redemption()` do not have side effects and are the correct way to
preview costs.

Guidance for applications that expose those methods:

- Validate symbol, side, market, settlement term, quantity or notional, limit
  price, and account before calling them; require an explicit human
  confirmation for anything that moves money.
- **Use the idempotency keys.** `create_order()`, `create_repo()`,
  `subscribe_fund()` and `redeem_fund()` accept `idempotency_key`, sent as the
  `X-Idempotency-Key` header. When omitted, the client generates a UUID v4, so
  two calls are two operations. Persist a key per intended operation and reuse
  it when retrying the same submission.
- Never retry an uncertain write. A timeout or a 5xx does not prove the
  operation was rejected; query `get_trading_operations()` or
  `get_account_activities()` before submitting again.
- Log the returned `order_id` / `transaction_id` for reconciliation, and the
  `trace_id` of any `IOLAPIError` for support.

## Response Process

Maintainers will acknowledge a private report when possible, investigate its
impact, and coordinate a fix or mitigation. Please allow reasonable time for
assessment and disclosure coordination before making details public.
