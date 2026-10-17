# Setup

## Native development

Use Python 3.12, Node.js 22, MySQL 8, and optionally Docker Desktop for Letta,
PostgreSQL and Redis. Use an empty development database, never a production DB.

1. Copy `backend/.env.example` to `backend/.env`. Set `DB_HOST`, `DB_PORT`,
   `DB_USER`, `DB_PASSWORD`, `DB_NAME` for that database.
2. Generate a JWT key with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   and put it in `SECRET_KEY`. Use `ENVIRONMENT=development` locally.
3. From the repository root:

```bash
python -m venv backend/venv
# Windows: backend/venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/venv/bin/python -m pip install -r backend/requirements-dev.txt
cd backend
venv/bin/python -m app.db.init_db
venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open <http://localhost:3000>. FastAPI serves <http://localhost:8000/docs>.
Next.js proxies API requests to `BACKEND_INTERNAL_URL` (default
`http://localhost:8000`). No frontend secrets are required. Templates contain
placeholders only; keep populated `.env` files out of Git.

## Docker development

Copy root `.env.example` to `.env` for Compose interpolation and configure
`MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`, `POSTGRES_PASSWORD`, and `ENVIRONMENT`.
Copy `backend/.env.example` to `backend/.env` for application credentials,
including a generated JWT key and optional Google/AI settings.
Use URL-safe generated PostgreSQL credentials because Letta's connection URI
interpolates that value. Compose supplies the backend MySQL password from the
root `MYSQL_ROOT_PASSWORD`; match the database's actual credential.

The checked-in Compose file intentionally references an existing **external
MySQL volume**. It is not a clean-room verification stack. Review its volume
binding before starting it; for a new development installation configure a
separate named volume. Do not reuse that volume for tests or migration rehearsals.
Changing `.env` does not change credentials inside an existing MySQL/PostgreSQL
volume: rotate them in the database separately and update consumers together.

After configuring a development volume and credentials, run `docker compose up
--build`. The frontend/backend are on 3000/8000. MySQL publishes 3307; a native
backend using that Docker DB must set `DB_PORT=3307`. Containerized backend uses
`mysql:3306`. Letta uses port 8283 inside the stack; inspect
`docker-compose.override.yml` for optional published infrastructure ports.
`./start.sh --frontend` is the Bash development convenience entry point; review
its configuration before use. Startup runs table creation, pending migrations
and catalog seeding. It never creates a demo family account.

## Authentication and proxy settings

- `ENVIRONMENT`: `development`, `test`, or `production`. Production rejects the
  known fallback/placeholder `SECRET_KEY` and keys shorter than 32 characters.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT lifetime, default 10080 (7 days).
  Password changes increment `token_version`, invalidating all older JWTs.
- `TRUSTED_PROXY_HOSTS`: comma-separated proxy peer IPs/CIDRs, **empty by default**.
  `X-Forwarded-For` is ignored unless the direct peer is trusted. Configure the
  actual Next.js/ingress proxy addresses; do not trust arbitrary client networks
  or `*`. Launch Uvicorn with `--no-proxy-headers` so only the app processes trust.
  Without this setting, proxied clients share the proxy's per-IP quota.
- Limits: login 20/min/IP, parent signup 5/min/IP, child creation 10/min/IP **and**
  10/min/authenticated parent. Google entry/callback also use auth limits.
  Each limiter is in memory and resets on restart.
- Google: set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`
  (e.g. `http://localhost:8000/api/auth/google/callback`) and `FRONTEND_URL`.
  The state cookie is Secure; use HTTPS for reliable full OAuth testing.
  Unknown student emails are rejected; parent signup via Google is supported.
- AI/voice/Letta provider settings are optional for auth verification; see the
  backend template. Provider failures do not roll back committed child creation.

## Verify

```bash
backend/venv/bin/python -m pytest backend/tests -q
backend/venv/bin/python backend/scripts/verify_frontend_contract.py
backend/venv/bin/python backend/scripts/verify_migration_parent_first.py
cd frontend
node --test tests/*.test.mjs
npm run lint
npm run build
```

On Windows substitute `backend/venv/Scripts/python.exe` for the interpreter.
The MySQL verification script starts its own labelled MySQL 8 tmpfs container,
restores a synthetic pre-0008 dump, upgrades it and removes the container. It
never uses configured app credentials, Compose, or existing volumes. The JSON
report lives in `docs/verification/parent-first-migration.json`.

The HTTP smoke scripts are for a running **disposable** loopback backend only:

```bash
backend/venv/bin/python backend/scripts/smoke_parent_flow.py http://127.0.0.1:8000
backend/venv/bin/python backend/scripts/smoke_parent_dashboard.py http://127.0.0.1:8000
backend/venv/bin/python backend/scripts/smoke_application.py http://127.0.0.1:8000
```

They create synthetic accounts and leave fixtures for inspection. They exercise
parent registration -> child creation -> child login -> password change ->
onboarding access -> scoped tracking -> scope controls/revoke. The backend
end-to-end tests also run these same drivers against isolated test databases.
Avoid repeated smoke bursts against one IP within a minute (signup limits apply).

## Deployment

1. **Back up the database** and verify the backup can be restored. Record the
   current migration ledger and deployed configuration. Preserve credentials
   outside source control; rotate the historically committed credentials.
2. **Run migrations** using the new backend artifact, before serving new code:
   from `backend/`, `python -m app.db.init_db` (never `--reset`). This creates any
   missing tables, applies numbered migrations and seeds missing catalogs.
   Check `schema_migrations` contains `0008_parent_provisioned_students.sql` and
   `0009_account_sign_in_metadata.sql`. Serialize migration execution; do not
   race startup migrations across workers. MySQL DDL auto-commits and can lock
   large tables; rehearse on a representative copy and allow a maintenance window.
3. **Deploy the backend** with `ENVIRONMENT=production`, a generated JWT key,
   configured proxy trust and Uvicorn's `--no-proxy-headers`. Verify identity,
   parent-only creation, first-login enforcement and scope-filtered reads.
4. **Deploy the frontend**, then exercise parent signup/Add child, child password
   change/onboarding, Google login, sharing controls and logout in a browser.

The two new SQL files only add columns, an index and a foreign key. No legacy
row is activated, revoked, re-scoped or assigned a parent. Existing students,
including parentless students and Google accounts, keep IDs, roles and hashes;
`must_change_password=false`, `token_version=0`, with unknown provenance flags
left NULL. JWTs without a version claim are treated as version 0. New temporary
students must change password before normal APIs; a verified Google takeover
invalidates their temporary password and tokens instead. Legacy pending links
still require explicit unexpired approval, and revoked links stay revoked.

Coordinate auth/advisor limits at an ingress or in Redis **before using multiple
workers/replicas**: current counters are per process. Do not regard a worker's
limit as a global quota. Changing the JWT signing key logs everyone out. For an
application rollback, leave additive columns in place and assess the old code's
handling of temporary accounts/token versions; do not restore an older backend
that bypasses those checks while new temporary accounts exist. Restore backups
only as an explicit operational recovery decision, not as a routine rollback.
