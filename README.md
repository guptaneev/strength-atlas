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

## Testing

Run unit tests:

```bash
pytest
```

## Troubleshooting

- Missing `ATLAS_DATABASE_URL`: migrations and CLI DB commands will fail.
- Browser Use calls require `ATLAS_BROWSER_USE_API_KEY`.
- `atlas ingest discover` currently uses seed URLs directly until Browser Use discovery is wired.
