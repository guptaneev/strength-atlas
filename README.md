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

## Environment

Required environment variables:

- `ATLAS_DATABASE_URL` (Supabase Postgres connection string)
- `ATLAS_SUPABASE_URL`
- `ATLAS_SUPABASE_SERVICE_KEY`
- `ATLAS_SUPABASE_STORAGE_BUCKET`
- `ATLAS_BROWSER_USE_API_KEY`

Optional:

- `.env` file in the repo root for local development
- `ATLAS_BROWSER_USE_POLL_TIMEOUT_SECONDS` (default `300`)
- `ATLAS_BROWSER_USE_EXTRACT_MODEL_PRIMARY` (default `bu-mini`)
- `ATLAS_BROWSER_USE_EXTRACT_MODEL_FALLBACK` (default `bu-max`)
- `ATLAS_MAX_CRAWL_RETRIES` (default `2`, for Browser Use transient failures/timeouts)
- `ATLAS_OPS_PER_DOMAIN_LIMIT` (default `10`)
- `ATLAS_OPS_GLOBAL_LIMIT` (default `50`)
- `ATLAS_OPS_FAILURE_RATE_THRESHOLD` (default `0.35`)
- `ATLAS_OPS_RUNS_LEDGER_PATH` (default `var/atlas/runs.jsonl`)

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
atlas ops metrics --limit 20 --json
```

Search:

```bash
atlas search sources --query "bench"
atlas search programs --query "bench" --days-per-week 4
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

Validated with live runs on multiple domains (`strongerbyscience.com`, `barbellmedicine.com`):

- discover created candidate sources at domain scale
- extract + refresh produced structured payloads (`payload_type=object`)
- diagnose reported high parse confidence with no validation errors on validated pages
- search returned expected program/source rows after extraction
- bulk backfill command (`reextract-empty`) succeeded where empty-program sources existed

## Testing

Run unit tests:

```bash
pytest
```

## Local Cron Automation

Example cron entry to run automation every 2 hours:

```cron
0 */2 * * * cd /Users/neevgupta/browser-use-project && . .venv/bin/activate && atlas ops run --global-limit 25 >> /tmp/atlas-ops.log 2>&1
```

Recommended workflow:
- Start with `atlas ops dry-run --json`.
- Enable `atlas ops run` on cron after dry-run output looks correct.
- Monitor `atlas ops metrics --json` and ledger file (`var/atlas/runs.jsonl`).

## Troubleshooting

- Missing `ATLAS_DATABASE_URL`: migrations and CLI DB commands will fail.
- Browser Use calls require `ATLAS_BROWSER_USE_API_KEY`.
- If Browser Use tasks are slow, pass `--timeout-seconds` on ingest commands or set `ATLAS_BROWSER_USE_POLL_TIMEOUT_SECONDS`.
- Extraction uses strict structured output. If output is unstructured or low quality, the crawl retries and can fail terminally with validation errors.
- Extraction uses model fallback by attempt (`ATLAS_BROWSER_USE_EXTRACT_MODEL_PRIMARY` then `ATLAS_BROWSER_USE_EXTRACT_MODEL_FALLBACK`).
- If a crawl appears stuck, use `atlas crawl stop --crawl-id <id>` to stop it and release the domain lock.
- Ingest commands block if another crawl is already `pending`/`running` for the same domain.
- Crawl retries are automatic for transient Browser Use errors/timeouts up to `ATLAS_MAX_CRAWL_RETRIES`.
- Use `atlas ingest diagnose --source-id <id>` to inspect payload type, text length, program counts, and validation diagnostics.
- Use `atlas ingest reextract-empty --domain <domain>` to refresh succeeded sources whose latest document has zero programs.
- Use `atlas ops dry-run` before scheduled automation changes.
- Use `atlas ops run` for sequential pending + empty-program remediation with summary metrics.
- If `atlas ops run` exits with code `2`, failure rate exceeded threshold (`ATLAS_OPS_FAILURE_RATE_THRESHOLD`).
- If extraction fails with claims/program FK mismatch, upgrade to latest code; claim `program_id` references are now remapped to inserted program IDs.
- Typical crawl statuses:
  - `pending`: job created, not started yet
  - `running`: in progress (including retry attempts)
  - `succeeded`: completed successfully
  - `failed`: terminal failure, including operator stop
