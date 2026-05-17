---
purpose: Active implementation roadmap for the Strength Atlas CLI MVP
status: implemented-with-fullstack-mvp-extension
scope: CLI + API + web MVP
owner: Strength Atlas Maintainers
---

# Strength Atlas Full-Stack MVP Technical Plan

## Summary

Build the MVP around a Python operator CLI plus a FastAPI/web surface backed by Browser Use Cloud and hosted Supabase Postgres. The system ingests allowlisted strength-training sources, stores raw crawl artifacts, normalizes program data into relational tables, and supports structured plus full-text search and retrieval-grounded Ask responses. Public web users authenticate through Supabase Auth and Ask is quota-limited.

The concrete stack is:

- Runtime: `Python 3.12`
- CLI framework: `Typer`
- Browser automation: `browser-use-sdk/v3`
- Data validation: `Pydantic v2`
- Database access: `SQLAlchemy 2` + `psycopg`
- Migrations: `Alembic`
- Hosted backend: `Supabase Postgres`
- Artifact storage: `Supabase Storage`
- Parsing and utilities: `BeautifulSoup4`, `readability-lxml`, `orjson`
- Logging and output: standard structured logging + `Rich`
- Testing: `pytest`

## Implementation Changes

### 1. Repository and package structure

Create one Python package with these directories:

- `src/atlas/cli` for Typer commands
- `src/atlas/browser_use` for the Browser Use adapter
- `src/atlas/db` for models, queries, and migrations wiring
- `src/atlas/ingest` for discovery, extraction, refresh, normalization
- `src/atlas/search` for query parsing and result ranking
- `src/atlas/storage` for Supabase Storage artifact handling
- `src/atlas/config` for environment and settings loading

Keep one executable entrypoint: `atlas`.

### 2. Hosted backend and persistence

Use Supabase-hosted Postgres as the system of record.

Do not use `pgvector` in this MVP. Search is implemented with Postgres full-text search plus explicit structured filters.

Use Supabase Storage for raw crawl artifacts. Store at minimum:

- `raw.html`
- `extracted.json`

Use stable object paths:

- `sources/{source_id}/crawls/{crawl_id}/raw.html`
- `sources/{source_id}/crawls/{crawl_id}/extracted.json`

### 3. Database schema

Implement exactly these tables for the MVP:

- `domains`
- `sources`
- `documents`
- `programs`
- `claims`
- `crawl_jobs`

`domains` fields:

- `id`
- `domain`
- `allowlisted`
- `paused`
- `notes`
- `created_at`
- `updated_at`

`sources` fields:

- `id`
- `url`
- `canonical_url`
- `domain_id`
- `source_type`
- `title`
- `author`
- `status`
- `last_crawled_at`
- `latest_document_id`
- `created_at`
- `updated_at`

`documents` fields:

- `id`
- `source_id`
- `crawl_job_id`
- `published_at`
- `raw_text`
- `html_storage_path`
- `extracted_json_storage_path`
- `parse_confidence`
- `content_tsv`
- `created_at`

`programs` fields:

- `id`
- `document_id`
- `name`
- `coach_name`
- `days_per_week`
- `specialization`
- `experience_level`
- `progression_type`
- `split_type`
- `summary`
- `confidence`
- `created_at`
- `updated_at`

`claims` fields:

- `id`
- `document_id`
- `program_id`
- `claim_type`
- `raw_text`
- `normalized_value`
- `confidence`
- `created_at`

`crawl_jobs` fields:

- `id`
- `job_type`
- `source_id`
- `target_url`
- `status`
- `retry_count`
- `browser_use_session_id`
- `browser_use_live_url`
- `browser_use_cost_usd`
- `started_at`
- `completed_at`
- `error_message`

### 4. Browser Use integration

Standardize on `browser-use-sdk/v3`.

Implement one adapter module that exposes exactly three operations:

- `discover_urls(domain: str, seed_urls: list[str])`
- `extract_url(url: str)`
- `refresh_source(source_id: str)`

Extraction adapter hardening:

- enforce structured extraction output schema
- retry transient and validation failures up to retry budget
- support model fallback by attempt (primary then fallback)
- persist Browser Use metadata for terminal outcomes

Use `run()` for discovery tasks on messy sites.

Use explicit session creation and reuse for direct extraction when a source requires multiple navigation steps.

Persist Browser Use metadata from every run into `crawl_jobs`.

Do not call Browser Use from search commands. Crawling is strictly offline and operator-triggered.

### 5. Ingestion and normalization pipeline

Discovery flow:

- validate the domain is allowlisted and not paused
- run Browser Use against provided seed URLs
- collect candidate URLs
- apply URL policy guardrails to discard low-value/system/taxonomy/assets
- cap accepted discovery candidates per run
- canonicalize URLs
- discard duplicates already present by `canonical_url`
- create new `sources` rows with `status='pending'`

Extraction flow:

- create a `crawl_jobs` row
- fetch the target page with Browser Use
- persist `raw.html` and `extracted.json` to Supabase Storage
- normalize title, author, source type, and main text into `documents`
- parse programs and claims into `programs` and `claims`
- validate extraction quality before DB write (`schema_invalid`, `low_quality_output`, `no_programs_on_program_page`)
- map claim `program_id` references to inserted DB program IDs (invalid references become `null`)
- write a weighted `tsvector` into `documents.content_tsv` from title + summary + raw text
- update `sources.latest_document_id`, `last_crawled_at`, and `status`

Refresh flow:

- rerun extraction for an existing `source_id`
- create a new `documents` row instead of mutating old documents
- replace the source's `latest_document_id`

Keep normalization deterministic and rule-based. No external LLM is used in this MVP outside Browser Use acquisition.

Operator diagnostics and backfill:

- `ingest diagnose` inspects extraction payload quality for a source/crawl
- `ingest reextract-empty` bulk-refreshes succeeded sources with zero programs

### 6. Search implementation

Implement two search modes:

- program search
- source search

Program search supports these filters:

- `days_per_week`
- `specialization`
- `experience_level`
- `progression_type`
- `split_type`
- `domain`

Ranking logic is fixed:

- exact structured filter matches first
- full-text rank second
- higher-confidence programs break ties
- newest crawl breaks remaining ties

Source search uses Postgres full-text search over `documents.content_tsv` with optional `domain` filter.

The CLI returns both machine-readable JSON and human-readable table output.

### 7. CLI surface

Implement these commands:

- `atlas domain add <domain>`
- `atlas domain list`
- `atlas domain pause <domain>`
- `atlas domain resume <domain>`
- `atlas ingest discover --domain <domain> --seed-url <url>...`
- `atlas ingest extract --url <url>`
- `atlas ingest refresh --source-id <id>`
- `atlas ingest diagnose --source-id <id> | --crawl-id <id>`
- `atlas ingest reextract-empty --domain <domain> [--limit <n>]`
- `atlas crawl list`
- `atlas source list`
- `atlas source show --source-id <id>`
- `atlas search programs --query <text> [filters...]`
- `atlas search sources --query <text> [--domain <domain>]`
- `atlas ops run [automation flags]`
- `atlas ops dry-run [automation flags]`
- `atlas ops metrics [--limit <n>]`
- `atlas ops domain-quality [--domain <domain>] [--domain-policy-file <path>]`
- `atlas search eval --fixture <path>`

Every command must support `--json`.

Ops scale-up controls:

- support optional domain policy file for domain-specific seed URLs and per-domain limits
- support optional domain admission thresholds in policy file to gate unstable/low-quality domains from continuous runs
- keep explicit operator caps (`--per-domain-limit`, `--global-limit`) as hard upper bounds

`atlas source show` must display:

- source metadata
- latest crawl status
- linked programs
- artifact storage paths

### 8. Operational rules

- Only allowlisted domains may be crawled.
- One active crawl per domain at a time.
- Maximum retries per crawl job: `2`.
- No automatic recrawl schedule in the MVP.
- No crawl-on-search behavior.
- When data is insufficient for a query, search returns empty or low-result output; it does not trigger a crawl.
- Operators refresh sources manually with CLI commands.
- Scheduled automation is external-orchestrated (for example cron) and uses `atlas ops run`; this does not add an in-app scheduler service.

### 9. Automation ledger and summary metrics

`atlas ops run` writes one JSON line per run to `var/atlas/runs.jsonl` (configurable).

Each run record includes:

- `run_id`, `started_at`, `completed_at`, `policy`
- `totals` for throughput, quality, reliability, and cost
- `by_domain` aggregate breakdown
- normalized `errors`
- per-item outcomes in `items`

Failure policy:

- exit code `2` when run failure rate exceeds the configured threshold
- exit code `0` otherwise

## Public Interfaces and Contracts

CLI is the only public interface in the MVP.

Output contracts to keep stable:

- `ProgramSearchResult`
- `SourceSearchResult`
- `SourceDetail`
- `CrawlJobStatus`

Required contract rules:

- every `ProgramSearchResult` includes `source_id`, `document_id`, `canonical_url`, and `confidence`
- every `SourceDetail` includes artifact paths and latest crawl metadata
- every search command supports both human-readable output and `--json`
- search never mutates crawl state

## Test Plan

- Migration tests for all six tables and expected indexes.
- Browser Use adapter tests for discovery, extraction success, extraction failure, and metadata persistence.
- URL canonicalization and dedupe tests across representative source URL variants.
- Normalization tests for expected parsing of title, author, programs, claims, and confidence scores from a fixed sample corpus.
- Search tests for:
  - free-text source search
  - program search with one filter
  - program search with multiple filters
  - ranking tie-breaks by confidence and recency
  - empty-result behavior
- extraction validation tests for unstructured/low-quality payloads
- discovery URL policy tests (blocked paths/assets/candidate cap)
- claim-to-program reference remapping tests (0/1-based local refs and invalid refs)
- error classification tests for common terminal/retryable buckets
- ops summary tests ensuring domain-gate blocked events are counted in totals
- CLI tests for all commands, including `--json` output.
- Storage tests ensuring `raw.html` and `extracted.json` are written to the expected bucket paths and linked from `documents`.

## Assumptions and Defaults

- The MVP is an operator-run CLI, not a user-facing product.
- Browser Use is used only for acquisition and extraction, not for search-time operations.
- Supabase is the hosted backend of record for both Postgres and artifact storage.
- Search is full-text plus structured filtering only; semantic retrieval and Ask are deferred.
- Public web auth and Ask quota enforcement are included in this MVP.
- No web-based ingest/ops admin UI is included; crawl operations remain operator CLI workflows.
- No in-app scheduler or automatic crawl-on-search behavior is included.

## CLI Usage Notes

See `README.md` for environment setup, migrations, and CLI examples.
