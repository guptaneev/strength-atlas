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
```

Expected outcomes:
- Discover creates pending sources and a `discover` crawl job.
- Extract creates a document and updates source status/last crawl.
- `source show` includes artifact paths plus latest crawl metadata.
- Search returns indexed rows once extraction is complete.

## Testing

Run unit tests:

```bash
pytest
```

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
- Typical crawl statuses:
  - `pending`: job created, not started yet
  - `running`: in progress (including retry attempts)
  - `succeeded`: completed successfully
  - `failed`: terminal failure, including operator stop
