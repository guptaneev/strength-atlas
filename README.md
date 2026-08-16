# Strength Atlas

**Ask a training question, get an answer with the source behind it.**

Strength training advice online is unattributed by default. Strength Atlas crawls
coaching programs, normalizes their claims into a structured corpus, and serves
retrieval-grounded answers where every claim links back to where it came from.

[Live app](https://strength-atlas-5bejgqq6uq-uc.a.run.app/app)

- 175+ programs, 476 claims, 83 sources · ~99% crawl success
- Sub-200ms query latency on indexed data
- 120+ tests at ~95% coverage across API, auth, search, and ingestion
- Hardened: JWKS auth, IP/user rate limiting, lifetime quotas, CSP/HSTS

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
pip install -e ".[dev]"
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

## Production Deployment

The canonical production stack is a cost-bounded Google Cloud Run Docker
service plus Supabase Postgres, Auth, and raw crawl Storage. The learned
reranker is distributed through private Google Cloud Storage as a versioned,
checksummed release artifact and is never committed to ordinary Git. Render
remains a disabled legacy alternative.

Follow the single [production deployment guide](docs/operations/production-deployment.md)
for environment variables, migrations, model activation, smoke tests,
monitoring, acceptance criteria, and application/database/model rollback.

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
- `configs/cloud-run.env.example.yaml`
- `scripts/deploy_cloud_run.sh`
- `render.yaml` (disabled legacy alternative)
- `.github/workflows/ci.yml`
- `docs/operations/ops-runbook.md`
