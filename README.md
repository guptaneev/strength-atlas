# Strength Atlas Full-Stack MVP

Strength Atlas is a production-oriented MVP for ingesting strength-training content, normalizing it into a queryable corpus, and serving search + grounded Ask responses through a web app and API.

This repository includes:
- operator CLI for ingestion/crawl/ops automation
- FastAPI backend for auth, quota-gated Ask, and search/source APIs
- modern static web UI served at `/app`
- Supabase-backed Postgres, Storage, and Auth integration

## Current Status

As of **May 17, 2026**:
- Full-stack MVP is implemented on `master`.
- API + web UI are integrated and launchable.
- Security baseline and deploy artifacts are present (`Dockerfile`, `render.yaml`, CI workflow, `SECURITY.md`).
- Test suite is green locally (`120 passed`).

## Architecture At A Glance

- Runtime: Python 3.12
- Backend/API: FastAPI + Uvicorn
- CLI: Typer
- ORM/migrations: SQLAlchemy 2 + Alembic + Psycopg
- Data platform: Supabase Postgres + Storage + Auth (JWT/JWKS)
- Ingestion engine: Browser Use SDK
- Frontend: server-hosted HTML/CSS/JS at `src/atlas/web`

High-level flow:
1. Operator discovers/extracts content with `atlas` CLI.
2. Normalized artifacts are persisted in Postgres + Supabase Storage.
3. End users sign up/sign in via Supabase auth-backed API endpoints.
4. Users query `/ask/*` and `/search/*` through web UI or API.
5. Ask requests are JWT-authenticated, rate limited, and quota enforced (default 5 lifetime).

## Quickstart (Local)

1. Create and activate virtualenv:
```bash
python -m venv .venv
. .venv/bin/activate
```

2. Install:
```bash
pip install -e .
```

3. Configure env:
```bash
cp .env.example .env
# fill ATLAS_* values
```

4. Run DB migrations:
```bash
alembic -c alembic.ini upgrade head
```

5. Start API/web:
```bash
atlas-api
# or: uvicorn atlas.api.app:app --host 0.0.0.0 --port 8000
```

6. Open app:
- [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app)

## Required Environment Variables

- `ATLAS_DATABASE_URL`
- `ATLAS_SUPABASE_URL`
- `ATLAS_SUPABASE_PUBLISHABLE_KEY`
- `ATLAS_SUPABASE_SERVICE_KEY`
- `ATLAS_SUPABASE_STORAGE_BUCKET`
- `ATLAS_BROWSER_USE_API_KEY`

Important optional controls:
- `ATLAS_APP_ENV` (`development` or `production`)
- `ATLAS_CORS_ALLOWED_ORIGINS`
- `ATLAS_TRUSTED_HOSTS`
- `ATLAS_ENFORCE_HTTPS_REDIRECT`
- `ATLAS_API_DOCS_ENABLED`
- `ATLAS_ASK_LIFETIME_LIMIT` (default `5`)
- `ATLAS_ASK_IP_RATE_LIMIT_WINDOW_SECONDS`
- `ATLAS_ASK_IP_RATE_LIMIT_MAX_REQUESTS`
- `ATLAS_ASK_USER_RATE_LIMIT_WINDOW_SECONDS`
- `ATLAS_ASK_USER_RATE_LIMIT_MAX_REQUESTS`
- `ATLAS_ASK_REQUEST_TIMEOUT_SECONDS`
- `ATLAS_REQUEST_MAX_BODY_BYTES`
- `ATLAS_ASK_CONTACT_CTA_URL`

## CLI Commands

Domain management:
```bash
atlas domain add example.com
atlas domain list
atlas domain pause example.com
atlas domain resume example.com
```

Ingestion:
```bash
atlas ingest discover --domain example.com --seed-url https://example.com
atlas ingest extract --url https://example.com/program
atlas ingest refresh --source-id 123
atlas ingest diagnose --source-id 123
atlas ingest reextract-empty --domain example.com --limit 10
```

Ops automation:
```bash
atlas ops dry-run --json
atlas ops run --json
atlas ops metrics --limit 20 --json
atlas ops backlog --json
atlas ops domain-quality --domain-policy-file docs/engineering/domain-crawl-policies.example.json --json
```

Search:
```bash
atlas search sources --query "bench"
atlas search programs --query "bench" --days-per-week 4
atlas search eval --fixture docs/engineering/search-eval-fixture.json --min-pass-rate 0.8
```

## API Surface

Public read/search:
- `GET /health`
- `GET /ready`
- `GET /dashboard/summary`
- `GET /search/sources`
- `GET /search/programs`
- `GET /sources`
- `GET /sources/{source_id}`

Auth:
- `POST /auth/signup`
- `POST /auth/login`

Authenticated Ask + quota:
- `GET /me/quota`
- `POST /ask/retrieve`
- `POST /ask/retrieve/debug`
- `POST /ask/answer`

Ask endpoints require `Authorization: Bearer <access_token>` and enforce lifetime quota + rate limits.

## Web UI MVP Features

- Sign up/sign in
- Quota indicator (5 lifetime asks by default)
- Ask workflow with grounded answer presentation
- Program/source search and source detail
- Dashboard summary
- Post-limit contact CTA behavior

## Testing

Run full test suite:
```bash
pytest
```

## Deployment

Production deployment target:
- Render (web service/API) + Supabase (Postgres/Storage/Auth)

Repo deployment assets:
- `/Users/neevgupta/browser-use-project/Dockerfile`
- `/Users/neevgupta/browser-use-project/render.yaml`
- `/Users/neevgupta/browser-use-project/.github/workflows/ci.yml`
- `/Users/neevgupta/browser-use-project/docs/operations/mvp-release-checklist.md`
- `/Users/neevgupta/browser-use-project/docs/operations/master-publish-checklist.md`

Production requirements:
- set explicit CORS and trusted hosts (no wildcard CORS)
- disable API docs in prod (`ATLAS_API_DOCS_ENABLED=false`)
- enforce HTTPS redirect (`ATLAS_ENFORCE_HTTPS_REDIRECT=true`)
- rotate any leaked keys immediately

## Security

- See `/Users/neevgupta/browser-use-project/SECURITY.md` for disclosure and hardening policy.
- Never commit `.env` or real credentials.
- Use least-privilege keys in hosted environments.

## Operations Runbook

- `/Users/neevgupta/browser-use-project/docs/operations/ops-runbook.md`
- `/Users/neevgupta/browser-use-project/docs/operations/mvp-release-checklist.md`
- `/Users/neevgupta/browser-use-project/docs/operations/master-publish-checklist.md`

## License

UNLICENSED (private/internal usage by default).
