# Strength Atlas CLI MVP

Operator-focused CLI for ingesting strength-training sources, normalizing data, and searching the indexed corpus.

## Quickstart

1. Create a Python 3.12 virtualenv and install dependencies:
   - `python -m venv .venv`
   - `. .venv/bin/activate`
   - `pip install -e .`
2. Set environment variables (see below).
3. Initialize the database with Alembic migrations.
4. Run CLI commands.

## Requirements

- Python 3.12
- Supabase Postgres
- Supabase Storage bucket
- Browser Use API key
- Supabase Auth users (for Ask endpoints)

## Environment

Required environment variables:

- `ATLAS_DATABASE_URL` (Supabase Postgres connection string)
- `ATLAS_SUPABASE_URL`
- `ATLAS_SUPABASE_PUBLISHABLE_KEY` (used server-side for `/auth/login`)
- `ATLAS_SUPABASE_SERVICE_KEY`
- `ATLAS_SUPABASE_STORAGE_BUCKET`
- `ATLAS_BROWSER_USE_API_KEY`

Optional:

- `.env` file in the repo root for local development
- `ATLAS_BROWSER_USE_POLL_TIMEOUT_SECONDS` (default `300`)
- `ATLAS_BROWSER_USE_EXTRACT_MODEL_PRIMARY` (default `bu-mini`)
- `ATLAS_BROWSER_USE_EXTRACT_MODEL_FALLBACK` (default `bu-max`)
- `ATLAS_MAX_CRAWL_RETRIES` (default `2`, for Browser Use transient failures/timeouts)
- `ATLAS_DISCOVERY_MAX_CANDIDATES_PER_RUN` (default `200`)
- `ATLAS_DISCOVERY_BLOCKED_PATH_TOKENS` (comma-separated low-value path tokens)
- `ATLAS_OPS_PER_DOMAIN_LIMIT` (default `10`)
- `ATLAS_OPS_GLOBAL_LIMIT` (default `50`)
- `ATLAS_OPS_FAILURE_RATE_THRESHOLD` (default `0.35`)
- `ATLAS_OPS_RUNS_LEDGER_PATH` (default `var/atlas/runs.jsonl`)
- `ATLAS_RETRIEVAL_DEBUG_TRACE_PATH` (default `var/atlas/retrieval-debug.jsonl`)
- `ATLAS_APP_ENV` (`development` or `production`)
- `ATLAS_API_DOCS_ENABLED` (default `true`, automatically disabled in production)
- `ATLAS_CORS_ALLOWED_ORIGINS` (comma-separated allowlist)
- `ATLAS_TRUSTED_HOSTS` (comma-separated host allowlist)
- `ATLAS_ENFORCE_HTTPS_REDIRECT` (default `false`)
- `ATLAS_REQUEST_MAX_BODY_BYTES` (default `131072`)
- `ATLAS_ASK_REQUEST_TIMEOUT_SECONDS` (default `30`)
- `ATLAS_SUPABASE_JWT_AUDIENCE` (default `authenticated`)
- `ATLAS_SUPABASE_JWT_ISSUER` (optional; defaults to `<SUPABASE_URL>/auth/v1`)
- `ATLAS_SUPABASE_JWKS_URL` (optional; defaults to Supabase JWKS path)
- `ATLAS_ASK_LIFETIME_LIMIT` (default `5`)
- `ATLAS_ASK_IP_RATE_LIMIT_WINDOW_SECONDS` / `ATLAS_ASK_IP_RATE_LIMIT_MAX_REQUESTS`
- `ATLAS_ASK_USER_RATE_LIMIT_WINDOW_SECONDS` / `ATLAS_ASK_USER_RATE_LIMIT_MAX_REQUESTS`
- `ATLAS_ASK_CONTACT_CTA_URL` (default `mailto:support@strengthatlas.app`)

Security notes:

- Never commit `.env` or paste real credentials in docs/issues.
- Use placeholder values in examples only (for example `...`).
- Rotate keys immediately if a secret is ever exposed.

## Migrations

Create the initial migration once:

```bash
alembic -c alembic.ini revision --autogenerate -m "init"
```

Apply migrations:

```bash
alembic -c alembic.ini upgrade head
```

## CLI Usage

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
atlas ingest discover --domain example.com --seed-url https://example.com --timeout-seconds 900
atlas ingest extract --url https://example.com/program --timeout-seconds 900
```

Crawl operations:

```bash
atlas crawl list
atlas crawl stop --crawl-id 123
```

Ops automation:

```bash
atlas ops dry-run --json
atlas ops run --json
atlas ops run --domain strongerbyscience.com --per-domain-limit 5 --global-limit 20
atlas ops run --discover-first --discover-seed-url strongerbyscience.com=https://www.strongerbyscience.com
atlas ops run --domain-policy-file docs/engineering/domain-crawl-policies.example.json
atlas ops metrics --limit 20 --json
atlas ops backlog --json
atlas ops domain-quality --domain-policy-file docs/engineering/domain-crawl-policies.example.json --json
```

Search:

```bash
atlas search sources --query "bench"
atlas search programs --query "bench" --days-per-week 4
atlas search eval --fixture docs/engineering/search-eval-fixture.json
atlas search eval --fixture docs/engineering/search-eval-fixture.json --min-pass-rate 0.8
```

API (retrieval-only, no crawling required):

```bash
atlas-api
# or
uvicorn atlas.api.app:app --host 0.0.0.0 --port 8000
```

Web UI:

- Open `http://127.0.0.1:8000/app` after starting `atlas-api`.
- The UI supports:
  - Supabase email/password sign-up and sign-in
  - quota indicator and post-limit contact CTA
  - corpus dashboard summary
  - Ask Atlas answer generation
  - program/source search
  - source list + source detail inspection

Example API calls:

```bash
curl -s "http://127.0.0.1:8000/search/sources?query=bench"
curl -s "http://127.0.0.1:8000/search/programs?query=bench&domain=strongerbyscience.com"
curl -s "http://127.0.0.1:8000/sources?status=pending&limit=20"
curl -s "http://127.0.0.1:8000/sources/1"
curl -s "http://127.0.0.1:8000/dashboard/summary"
curl -s -X POST "http://127.0.0.1:8000/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"..."}'
curl -s -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"..."}'
curl -s -X POST "http://127.0.0.1:8000/ask/retrieve" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"bench frequency","max_sources":5,"max_programs":10,"filters":{"domain":"strongerbyscience.com"}}'
curl -s -X POST "http://127.0.0.1:8000/ask/retrieve/debug" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"bench frequency","max_sources":5,"max_programs":10,"filters":{"domain":"strongerbyscience.com"}}'
curl -s -X POST "http://127.0.0.1:8000/ask/answer" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"bench frequency","max_sources":5,"max_programs":10,"include_evidence":true,"filters":{"domain":"strongerbyscience.com"}}'
curl -s "http://127.0.0.1:8000/me/quota" -H "Authorization: Bearer <access_token>"
```

JSON output:

```bash
atlas search sources --query "bench" --json
```

## Validation Workflow

Run this end-to-end check after setup:

```bash
atlas domain add strongerbyscience.com
atlas ingest discover --domain strongerbyscience.com --seed-url https://www.strongerbyscience.com --timeout-seconds 900
atlas source list --json
atlas ingest extract --url https://www.strongerbyscience.com/how-to-bench --timeout-seconds 900
atlas source show --source-id 1 --json
atlas ingest diagnose --source-id 1 --json
atlas crawl list --json
atlas search sources --query bench --domain strongerbyscience.com --json
atlas search programs --query bench --domain strongerbyscience.com --json
atlas ops dry-run --domain strongerbyscience.com --json
atlas ops run --domain strongerbyscience.com --per-domain-limit 3 --global-limit 10 --json
atlas ops metrics --limit 5 --json
```

Expected outcomes:
- Discover creates pending sources and a `discover` crawl job.
- Extract creates a document and updates source status/last crawl.
- `source show` includes artifact paths plus latest crawl metadata.
- Search returns indexed rows once extraction is complete.

## Current Validation Status

Validated with live runs on multiple domains (`strongerbyscience.com`, `barbellmedicine.com`) and the current production snapshot as of **2026-04-24**:

- discover created candidate sources at domain scale
- extract + refresh produced structured payloads (`payload_type=object`)
- diagnose reported high parse confidence with no validation errors on validated pages
- search returned expected program/source rows after extraction
- bulk backfill command (`reextract-empty`) succeeded where empty-program sources existed
- live DB snapshot: `sources=83` (`succeeded=39`, `pending=44`), `documents=50`, `programs=175`, `claims=476`
- latest successful crawl timestamp: `2026-04-14T21:00:54+00:00`
- latest 20 crawls: `0` failed

## Testing

Run unit tests:

```bash
pytest
```

## Deployment (Render)

This repo includes:

- `Dockerfile` for production API/web image
- `render.yaml` blueprint for a Render web service
- `.github/workflows/ci.yml` for tests + secret scanning

Render notes:

- Set all `ATLAS_*` runtime env vars in Render (database/auth keys must be set manually).
- Keep `ATLAS_API_DOCS_ENABLED=false` and `ATLAS_ENFORCE_HTTPS_REDIRECT=true` in production.
- Configure `ATLAS_CORS_ALLOWED_ORIGINS` and `ATLAS_TRUSTED_HOSTS` to exact production domains.

Release/rollback checklist is documented in:
- [`docs/operations/mvp-release-checklist.md`](docs/operations/mvp-release-checklist.md)
- [`docs/operations/ops-runbook.md`](docs/operations/ops-runbook.md)

## Local Cron Automation

Example cron entry to run automation every 2 hours:

```cron
0 */2 * * * cd /path/to/browser-use-project && . .venv/bin/activate && atlas ops run --global-limit 25 >> /tmp/atlas-ops.log 2>&1
```

Recommended workflow:
- Start with `atlas ops dry-run --json`.
- Enable `atlas ops run` on cron after dry-run output looks correct.
- Monitor `atlas ops metrics --json` and ledger file (`var/atlas/runs.jsonl`).

## Troubleshooting

- Missing `ATLAS_DATABASE_URL`: migrations and CLI DB commands will fail.
- Browser Use calls require `ATLAS_BROWSER_USE_API_KEY`.
- Ask endpoints require `Authorization: Bearer <supabase_access_token>`.
- `/auth/login` requires `ATLAS_SUPABASE_PUBLISHABLE_KEY` configured server-side.
- Ask quota defaults to 5 lifetime requests per user (`ATLAS_ASK_LIFETIME_LIMIT`).
- If Browser Use tasks are slow, pass `--timeout-seconds` on ingest commands or set `ATLAS_BROWSER_USE_POLL_TIMEOUT_SECONDS`.
- Extraction uses strict structured output. If output is unstructured or low quality, the crawl retries and can fail terminally with validation errors.
- Extraction uses model fallback by attempt (`ATLAS_BROWSER_USE_EXTRACT_MODEL_PRIMARY` then `ATLAS_BROWSER_USE_EXTRACT_MODEL_FALLBACK`).
- If a crawl appears stuck, use `atlas crawl stop --crawl-id <id>` to stop it and release the domain lock.
- Ingest commands block if another crawl is already `pending`/`running` for the same domain.
- Crawl retries are automatic for transient Browser Use errors/timeouts up to `ATLAS_MAX_CRAWL_RETRIES`.
- Discovery applies URL guardrails to reduce low-value fanout and caps candidates per run.
- Use `atlas ingest diagnose --source-id <id>` to inspect payload type, text length, program counts, and validation diagnostics.
- Use `atlas ingest reextract-empty --domain <domain>` to refresh succeeded sources whose latest document has zero programs.
- Use `atlas ops dry-run` before scheduled automation changes.
- Use `atlas ops run` for sequential pending + empty-program remediation with summary metrics.
- Use `atlas ops run --domain-policy-file <path>` for domain-specific seed strategy and per-domain limits.
- Domain policy files can also enforce admission thresholds per domain (`admission_*` keys) to block unstable/low-quality domains from continuous runs.
- Use `atlas ops backlog --json` to inspect pending backlog, stale succeeded sources, and per-domain samples.
- If `atlas ops run` exits with code `2`, failure rate exceeded threshold (`ATLAS_OPS_FAILURE_RATE_THRESHOLD`).
- `atlas ops` summaries include `blocked_domain_gates` so domain-level blocking events are visible in run totals.
- Failure taxonomy now classifies DB truncation, DNS failures, and rate limits explicitly (instead of generic terminal errors).
- If all API routes return `400` under custom domains, verify `ATLAS_TRUSTED_HOSTS` includes the request hostname.
- If extraction fails with claims/program FK mismatch, upgrade to latest code; claim `program_id` references are now remapped to inserted program IDs.
- Typical crawl statuses:
  - `pending`: job created, not started yet
  - `running`: in progress (including retry attempts)
  - `succeeded`: completed successfully
  - `failed`: terminal failure, including operator stop
