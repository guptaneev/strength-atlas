# Strength Atlas

Strength Atlas is a production-oriented training-intelligence platform that ingests strength-coaching content, normalizes it into a searchable corpus, and serves retrieval-grounded answers through API and web UI.

## What This Repo Contains

- `atlas` CLI for domain/source ingestion, crawl orchestration, and ops automation
- FastAPI backend for auth, quota-gated Ask endpoints, and search/source APIs
- Static web app served from `/app`
- Supabase-backed Postgres, Storage, and JWT auth integration

## Architecture

- Runtime: Python 3.12
- API: FastAPI + Uvicorn
- CLI: Typer
- Data: SQLAlchemy + Alembic + Psycopg
- Auth/Storage: Supabase
- Crawling/Extraction: Browser Use SDK

Core flow:
1. Operators discover/extract sources using `atlas` commands.
2. Sources/documents/program records are persisted in Postgres and Storage.
3. Users authenticate through Supabase-backed auth endpoints.
4. Users query `/ask/*` and `/search/*` from the app or API.

## Local Setup

1. Create and activate a virtual environment.
```bash
python -m venv .venv
. .venv/bin/activate
```

2. Install dependencies.
```bash
pip install -e .
```

3. Create environment file.
```bash
cp .env.example .env
```

4. Fill required values in `.env`.
- `ATLAS_DATABASE_URL`
- `ATLAS_SUPABASE_URL`
- `ATLAS_SUPABASE_PUBLISHABLE_KEY`
- `ATLAS_SUPABASE_SERVICE_KEY`
- `ATLAS_SUPABASE_STORAGE_BUCKET`
- `ATLAS_BROWSER_USE_API_KEY`

5. Run migrations.
```bash
alembic -c alembic.ini upgrade head
```

6. Start API + web app.
```bash
atlas-api
```

7. Open the app.
- `http://127.0.0.1:8000/app`

## Production Environment Configuration

Use this process for deployment targets (Render, containers, Kubernetes, etc.).

1. Create secrets in your platform secret manager.
- `ATLAS_DATABASE_URL`
- `ATLAS_SUPABASE_SERVICE_KEY`
- `ATLAS_BROWSER_USE_API_KEY`

2. Set non-secret config vars.
- `ATLAS_APP_ENV=production`
- `ATLAS_SUPABASE_URL=https://<project-ref>.supabase.co`
- `ATLAS_SUPABASE_PUBLISHABLE_KEY=<publishable-key>`
- `ATLAS_SUPABASE_STORAGE_BUCKET=<bucket>`
- `ATLAS_CORS_ALLOWED_ORIGINS=https://<your-web-origin>`
- `ATLAS_TRUSTED_HOSTS=<your-api-hostname>`
- `ATLAS_ENFORCE_HTTPS_REDIRECT=true`
- `ATLAS_API_DOCS_ENABLED=false`

3. Configure abuse and request controls.
- `ATLAS_REQUEST_MAX_BODY_BYTES`
- `ATLAS_ASK_REQUEST_TIMEOUT_SECONDS`
- `ATLAS_ASK_IP_RATE_LIMIT_WINDOW_SECONDS`
- `ATLAS_ASK_IP_RATE_LIMIT_MAX_REQUESTS`
- `ATLAS_ASK_USER_RATE_LIMIT_WINDOW_SECONDS`
- `ATLAS_ASK_USER_RATE_LIMIT_MAX_REQUESTS`
- `ATLAS_ASK_LIFETIME_LIMIT`

4. Deploy and run migrations before serving traffic.
```bash
alembic -c alembic.ini upgrade head
```

5. Verify readiness after deploy.
- `GET /health` should return `200`
- `GET /ready` should return `200`

## Security Baseline

This repo enforces a baseline aligned to common OWASP Top 10 controls:

- Input validation: bounded lengths and structured validators on auth/query/filter inputs
- Injection resistance: SQLAlchemy query construction (no string-concatenated SQL)
- Auth hardening: Bearer token verification with JWKS and controlled fallback
- Broken access control prevention: Ask and quota endpoints require auth
- Abuse controls: IP/user rate limiting and lifetime ask quota
- Security headers: CSP, HSTS (prod), frame deny, nosniff, permissions policy
- Request-size guardrails: maximum request body enforcement
- Safe UI rendering: DOM text insertion via `textContent` and safe external URL filtering

See `SECURITY.md` for disclosure and policy guidance.

## Common Commands

Run tests:
```bash
pytest
```

Start API directly:
```bash
uvicorn atlas.api.app:app --host 0.0.0.0 --port 8000
```

Run key CLI workflows:
```bash
atlas ingest discover --domain example.com --seed-url https://example.com
atlas ops dry-run --json
atlas search programs --query "bench"
```

## Troubleshooting

`/ready` returns degraded:
- Check DB connectivity and credentials in `ATLAS_DATABASE_URL`
- Verify Supabase URL and publishable key
- Confirm JWKS endpoint is reachable

Authentication failing:
- Confirm publishable key and project URL match the same Supabase project
- Confirm user exists and email/password are correct
- Check system clock skew in hosting environment

CORS or host errors:
- Ensure `ATLAS_CORS_ALLOWED_ORIGINS` exactly matches your frontend origin
- Ensure `ATLAS_TRUSTED_HOSTS` includes your API hostname

Rate limit or quota responses:
- Tune `ATLAS_ASK_*` limits for your traffic profile
- Use `/me/quota` to inspect user quota state

## Deployment Assets

- `Dockerfile`
- `render.yaml`
- `.github/workflows/ci.yml`
- `docs/operations/mvp-release-checklist.md`
- `docs/operations/master-publish-checklist.md`

## License

UNLICENSED (private/internal usage by default).
