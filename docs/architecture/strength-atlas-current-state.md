# Strength Atlas: Current State

This document is a readable map of the Strength Atlas repository as it exists today. It explains the product, the pipeline, the technologies, the important data objects, and the boundary between what is implemented now and what belongs to the future ML plan.

For detailed requirements and implementation contracts, see the [V1 PRD](../product/strength-atlas-prd-v1.md), [MVP technical plan](../engineering/strength-atlas-cli-mvp-technical-plan.md), and current [reranker reference](../engineering/reranker.md).

## What Strength Atlas is

Strength Atlas is a training-intelligence application. It collects strength-training material from the web, turns that material into structured records, and lets users search the resulting corpus with source-backed evidence.

The core value is traceability:

```text
coaching content on the web
        ↓
discovered and crawled sources
        ↓
normalized documents, programs, and claims
        ↓
searchable PostgreSQL corpus
        ↓
program results and evidence cards
        ↓
an answer that points back to source material
```

The system is currently a retrieval and ingestion platform with a thin grounded-answer layer. It is not yet a trained machine-learning ranking system or a generative question-answering system.

## Current user experience

The web application is served by the same FastAPI process as the API. A user can:

- sign up or sign in through Supabase-backed authentication;
- ask a training question;
- browse program search results;
- search sources;
- filter by domain and program metadata where available;
- inspect evidence cards and source links;
- view a dashboard summary of indexed content;
- inspect quota and authentication state.

The CLI is the operator-facing interface. It is used to manage domains, discover URLs, extract source content, refresh sources, inspect crawl state, run search, run search evaluation, and operate the crawl backlog.

## The end-to-end pipeline

### 1. Domain admission

An operator adds a domain to the database and controls whether it is allowlisted or paused. This keeps crawling within an explicit scope.

Relevant code:

- `src/atlas/cli/commands/domain.py`
- `src/atlas/ingest/url_policy.py`
- `src/atlas/ops/admission.py`
- `src/atlas/ops/policies.py`

### 2. URL discovery

The operator provides a domain and seed URLs. The Browser Use client asks Browser Use to find program-related pages. The result is parsed for candidate URLs, canonicalized, restricted to the target domain, filtered by URL policy, deduplicated, and stored as `sources`.

Each discovery operation creates a `crawl_jobs` record containing status, retries, Browser Use session metadata, live URL, and cost when available.

```text
domain + seed URLs
        ↓
Browser Use discovery session
        ↓
candidate URLs
        ↓
canonicalization + domain checks + blocked-path policy
        ↓
new Source rows with pending status
```

Relevant code:

- `src/atlas/ingest/discovery.py`
- `src/atlas/browser_use/client.py`
- `src/atlas/cli/commands/ingest.py`

### 3. Page extraction

For a source, the Browser Use client opens the URL and requests a structured JSON object containing title, author, source type, summary, main text, programs, and claims.

Extraction uses a primary Browser Use model and can retry with a fallback model. The result is validated before it is committed. Low-quality output, invalid schemas, and missing programs on program-focused pages can cause a retry or failure.

Raw HTML and structured extraction JSON are uploaded to Supabase Storage when storage is configured. The database keeps paths to those objects.

Relevant code:

- `src/atlas/ingest/extraction.py`
- `src/atlas/ingest/normalization.py`
- `src/atlas/browser_use/schemas.py`
- `src/atlas/storage/client.py`

### 4. Normalization and persistence

The extraction result is normalized into a consistent internal shape. The pipeline sanitizes short fields, handles JSON-like output, infers a basic program record for some program-focused pages, calculates parse confidence, and records warnings.

One extraction can create:

- one `document` containing the raw text and storage paths;
- zero or more `programs` with structured metadata;
- zero or more `claims` tied to the document and optionally a program;
- one completed or failed `crawl_job`.

The source is updated with its latest document, crawl timestamp, metadata, and status.

### 5. Search indexing

The document text, title, and summary are converted into a PostgreSQL English `tsvector` and indexed with a GIN index.

The current search implementation uses:

- PostgreSQL full-text matching and `ts_rank` for text relevance;
- exact structured filters for days per week, specialization, experience level, progression type, split type, and domain;
- URL page-quality heuristics that favor program/template/how-to pages and downweight category, tag, author, and broad “best” pages;
- parse confidence and recency as tie-breakers.

The repository now implements a fine-tuned cross-encoder reranker and a configurable serving boundary for both program and source-evidence candidates. Embedding generation, vector storage, and cosine-similarity retrieval are still not implemented.

### 6. Retrieval and evidence selection

An Ask request runs two searches:

1. Source search finds matching source pages.
2. Program search finds matching structured program records.

Program results are used to build evidence cards first. If no program evidence is available, matching sources are used as a fallback. Each evidence card can include a source URL, title, snippet from raw text, parse confidence, and crawl timestamp.

Retrieval debug responses preserve source candidates, program candidates, selected evidence, filters, and counts. A JSONL trace is written when possible, and trace failures do not block the user response.

```text
request validation
        ↓
source full-text search     program full-text + filter search
        └──────────────┬────────────────┘
                       ↓
                 evidence selection
                       ↓
              snippets + source metadata
```

Relevant code:

- `src/atlas/api/service.py`
- `src/atlas/search/sources.py`
- `src/atlas/search/programs.py`
- `src/atlas/ask/contracts.py`
- `src/atlas/api/traces.py`

### 7. Answer construction

The current `/ask/answer` endpoint does not call a language model. It builds a deterministic summary from the retrieved evidence: query, evidence count, program names, snippets, supporting domains, and average parse confidence.

If there is no evidence, it returns an `insufficient_evidence` response rather than inventing an answer. This is an intentional safety and grounding boundary. A future answer-generation model could be added after retrieval, but that is separate from the current search implementation.

## Technology stack

### Application layer

- Python 3.12+
- FastAPI for HTTP APIs and request lifecycle
- Uvicorn for local and production ASGI serving
- Typer for the `atlas` CLI
- Pydantic and Pydantic Settings for contracts and environment configuration

### Data layer

- PostgreSQL, accessed through SQLAlchemy and Psycopg
- Alembic for schema migrations
- PostgreSQL full-text search via `tsvector`, `plainto_tsquery`, and `ts_rank`
- Supabase Postgres and Storage integration

### Browser and extraction layer

- Browser Use SDK for discovery and page extraction
- Browser Use sessions provide status, live URLs, session IDs, and reported cost metadata
- Structured extraction is requested through a Pydantic output schema and validated before persistence

### Identity and security

- Supabase Auth for signup, login, and user identity
- JWT verification through JWKS with controlled fallback behavior
- Trusted hosts, CORS configuration, HTTPS redirect option, and security headers
- Request body limits, IP and user rate limits, and lifetime Ask quota

### Frontend

- Static HTML templates
- Plain JavaScript in `src/atlas/web/static/app.js`
- Plain CSS in `src/atlas/web/static/styles.css`
- The frontend calls the FastAPI endpoints and stores the auth token in browser local storage

### Testing and quality

- Pytest test suite across API, auth, search, ingestion, operations, migrations, and normalization
- Search evaluation fixture for relevance regression checks
- JSONL operational and retrieval-debug traces for local diagnostics

## The data model in plain English

```text
Domain
  └── Source
        └── Document
              ├── Program
              └── Claim

Source ── latest_document ──> Document
Source ── crawl history ────> CrawlJob
User ───────────────────────> AskQuotaUsage
```

### Domain

The site boundary. It records whether the domain is allowlisted or paused and contains operational notes.

### Source

A canonical URL discovered for a domain. It stores source metadata, status, and a pointer to the latest document.

### CrawlJob

An auditable discovery or extraction attempt. It stores status, retry count, errors, Browser Use session information, timestamps, and cost metadata.

### Document

The extracted page snapshot. It stores raw text, parse confidence, full-text search data, and paths to HTML and JSON artifacts in Supabase Storage.

### Program

A normalized training program extracted from a document. It can include coach, days per week, specialization, experience level, progression type, split type, summary, and confidence.

### Claim

A normalized coaching claim associated with a document and optionally a program. Claims are part of the corpus model, even though the current search UI is primarily program/source oriented.

### AskQuotaUsage

A per-user counter supporting the lifetime Ask limit.

## Main interfaces

### Operator CLI

Typical workflows include:

```text
atlas domain add/list/pause/resume
atlas ingest discover/extract/refresh/diagnose
atlas source list/show
atlas search programs/sources/eval
atlas crawl list/stop
atlas ops run/dry-run/metrics/backlog/domain-quality
```

### HTTP API

Important routes include:

```text
GET  /health
GET  /ready
POST /auth/login
POST /auth/signup
GET  /me/quota
GET  /search/sources
GET  /search/programs
GET  /sources
GET  /sources/{source_id}
GET  /dashboard/summary
POST /ask/retrieve
POST /ask/retrieve/debug
POST /ask/answer
```

Interactive API docs are available in non-production mode when enabled.

## Operational safeguards

The system treats crawling and user-facing Ask traffic as different types of work.

For crawling:

- domains must be explicitly managed;
- URL policy prevents out-of-domain and undesirable paths;
- per-domain and global operation limits are configurable;
- retries are limited and recorded;
- crawl jobs can be stopped and audited;
- Browser Use cost metadata is retained.

For Ask traffic:

- requests are schema-validated and bounded;
- authentication is required for protected Ask routes;
- IP and user rate limits are enforced in memory;
- a lifetime per-user quota is stored in PostgreSQL;
- timeout and request-body limits are configured;
- no-evidence responses are explicit rather than fabricated.

## Repository map

```text
src/atlas/
├── api/          FastAPI app, routes, auth, quotas, limits, service layer
├── ask/          Ask request and response contracts
├── browser_use/  Browser Use SDK adapter and extraction schemas
├── cli/          Typer application and operator commands
├── config/       Environment-backed settings
├── db/           SQLAlchemy models, engine, and migration support
├── ingest/       Discovery, extraction, normalization, retries, URL policy
├── ops/          Crawl planning, admission, backlog, ledger, and metrics
├── search/       Source/program PostgreSQL search and evaluation
├── storage/      Supabase Storage adapter and object paths
└── web/          Static frontend templates, JavaScript, and CSS

docs/
├── product/      Product intent and architecture context
├── engineering/ Active MVP plans, contracts, and integration references
├── roadmap/      Future ML implementation and learning plans
├── architecture/ Current-state system summaries
└── operations/  Release checklists and runbooks
```

## What is complete versus next

### Implemented now

- Browser Use-powered discovery and extraction
- Canonical source management and URL policy
- Normalized document, program, and claim persistence
- PostgreSQL full-text search and structured program filters
- Source-backed evidence cards and deterministic grounded summaries
- CLI and FastAPI interfaces
- Supabase Auth and Storage integration
- Crawl job auditing, retries, operations controls, and diagnostics
- Search evaluation fixtures and broad automated test coverage

### Not implemented yet

- Embedding generation and vector search
- Cosine-similarity retrieval baseline
- Human-judged reranker benchmarking beyond the current bootstrap benchmark
- Transformer fine-tuning or LoRA/PEFT
- A labeled query-document ranking dataset
- Statistical comparison of learned ranking against a vector baseline
- GPU, mixed-precision, batching, or quantized inference
- LLM-generated synthesis in `/ask/answer`
- Background worker infrastructure for long-running ingestion

These gaps are not accidental omissions in this summary. They define the starting point for the future ML roadmap and should be treated as hypotheses and implementation work, not as current capabilities.

## How to read the project as a learner

Use this order when getting familiar with the code:

1. Read the product summary and this document.
2. Trace `GET /search/programs` through the API service into `src/atlas/search/programs.py`.
3. Trace `atlas ingest extract` through extraction, normalization, and the database models.
4. Inspect one `CrawlJob`, `Source`, `Document`, and `Program` relationship.
5. Run the existing tests and search evaluation.
6. Read the current [reranker reference](../engineering/reranker.md) for training, evaluation, and serving details.

The most important distinction is this:

```text
current system: collect → normalize → full-text retrieve → show evidence
future ML work:  label → learn → evaluate → optimize → integrate
```

That distinction keeps the future experiment honest. The baseline should be measured from the system that actually exists, and each new ML component should earn its place through improved relevance and acceptable operational cost.
