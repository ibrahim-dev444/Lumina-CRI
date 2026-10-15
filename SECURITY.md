# Security in Lumina CRI

How Lumina protects the customer data it holds. Each point says where the rule lives, so it can be checked.

## Keeping organizations apart

- Every organization (bank) has its **own PostgreSQL schema**: its customers, users, connectors and audit log are in
  separate tables (`TENANT_APPS` in `backend/config/settings.py`). Requests reach an organization only through its
  `/t/<code>/` address. `backend/tenants/tests/test_isolation.py` checks tables, users, sessions and look-ups.
- The platform team signs in separately at `/platform`, sees counts only (never customer details), and can
  **suspend** an organization, which closes it to every request at once (`tenants/middleware.py`).

## Signing in

- Passwords are stored only as one-way **Argon2id** hashes; older PBKDF2 hashes are upgraded at the next sign-in.
  Nobody can read them back.
- **Rate limits** (`REST_FRAMEWORK` in settings, `api/throttles.py`): 10 sign-in attempts a minute per address,
  60 requests a minute when signed out, 600 when signed in, 120 push batches a minute per connector.
- **Lockout**: 5 wrong passwords lock that username for 15 minutes, for bank and platform logins
  (`accounts/lockout.py`). Every attempt is in the audit log.
- **Idle sign-out**: 30 minutes without activity ends the session (`SESSION_COOKIE_AGE`).
- New accounts and password resets give a **temporary password** that unlocks nothing until the person picks their own.
- Hosted: cookies are HTTPS-only, browsers are told to use HTTPS for a year (HSTS).

## Who sees what

- Roles and their capabilities are one table (`accounts/roles.py`), enforced by the server on every request; screens
  only hide what the server would refuse anyway. Refusals are logged.
- Front-line roles never receive AML risk, PEP or sanctions results (tipping off).
- Mobile, email and birth date are masked for agents; PAN, CKYC and Aadhaar are masked for everyone.

## Identity numbers

- PAN and CKYC are **encrypted** (Fernet, `FIELD_ENCRYPTION_KEY`) in the cleaned record and in the raw copy.
  Matching uses one-way fingerprints. Only the last 4 digits of Aadhaar are ever stored.
- Showing a full number needs the compliance role and a reason, and is logged (the number itself is not).

## Connectors

- Passwords, tokens and connection strings are encrypted, never returned to the browser, never logged.
- Connectors may only reach **public internet addresses**; private and internal addresses (the server's own network,
  cloud metadata) are refused (`security/network.py`). Database sessions are read-only, queries time out
  (`CONNECTOR_TIMEOUT_SECONDS`) and read at most `CONNECTOR_MAX_ROWS` rows. Only column names found by Discover are
  ever put in a query. API redirects are refused.
- **Push API keys** are shown once and stored as a SHA-256 hash; a wrong key and an unknown connector get the same
  answer. At most 1,000 records per request, every field checked.
- Scheduled syncs run only when the caller sends `SYNC_RUNNER_TOKEN`.

## Audit

- Every sign-in, view of a customer, export, merge, correction, reveal, consent change, user and settings change,
  connector change and refused request is written to an append-only log that the app cannot edit or delete.

## Browser protections

- API: `X-Frame-Options: DENY`, `nosniff`, same-origin referrer. Website (`frontend/vercel.json`): a Content Security
  Policy allowing only Lumina's own scripts, no framing, no camera or location access.

## Checks

- CI runs every test, and a dependency audit (`pip-audit`, `npm audit`) for known problems in libraries.

## Not done yet (known gaps)

- One encryption key for all organizations; per-organization keys would limit the damage of a leaked key.
- The hosted demo has no fixed outgoing IP address, so bank databases cannot restrict access by address.
- No two-factor sign-in yet.

Found a problem? Tell the project owner privately; do not open a public issue.

## Other safeguards

- Django's own admin pages are served only in development; on the hosted site every change goes through the app,
  where roles, lockout and the audit log apply.
- Customer exports guard against spreadsheet formulas: a cell starting with `=`, `+`, `-` or `@` opens as text.
- Uploads: at most 20 CSV files a request, 5 MB each, checked as UTF-8 CSV with a header and the mapped columns;
  file content is stored in the database, never on disk under the uploaded name. Logos: PNG, JPEG or WebP up to
  256 KB, checked by their content; SVG is refused.
- The production website ships no source maps. Dependencies are checked by `pip-audit` and `npm audit` in CI.
- Not yet: multi-factor sign-in.

