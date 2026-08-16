# Strength Atlas

**Evidence-backed strength-training research.**

Strength Atlas indexes public coaching material, normalizes it into a structured
corpus, and lets people find programs or inspect source-backed answers. Every
result keeps a link to its original material.

[Open the live app](https://strength-atlas-5bejgqq6uq-uc.a.run.app/app)

## What is here

- A FastAPI service and web app served together at `/app`
- An operator CLI for domain admission, discovery, extraction, normalization,
  search evaluation, model work, and controlled crawl operations
- Supabase Postgres for structured records, Supabase Auth for sign-in, and
  Supabase Storage for raw crawl artifacts
- A fine-tuned cross-encoder reranker released from private Google Cloud Storage
- A Google Cloud Run deployment with bounded cost, authenticated Ask requests,
  lifetime quotas, and IP and user rate limits

## How it works

1. Operators admit a domain and discover eligible URLs.
2. Browser Use extracts source material into validated structured records.
3. The service stores sources, documents, programs, claims, and crawl history.
4. Search retrieves structured and full-text candidates, then reranks them when
   the learned model is available.
5. Ask Atlas returns a deterministic, evidence-backed response with source
   cards. It does not invent a generative answer.

Read the [product scope](docs/product/strength-atlas-prd-v1.md),
[architecture](docs/architecture/strength-atlas-current-state.md), and
[documentation index](docs/README.md) for the maintained detail.

## Local setup

Requirements: Python 3.12 or later, a Postgres-compatible database, and the
service credentials described in `.env.example`.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic -c alembic.ini upgrade head
atlas-api
```

Open `http://127.0.0.1:8000/app`.

For a complete local environment, set the database, Supabase, storage, and
Browser Use values in `.env`. The Ask surface requires Supabase Auth; public
program and source search do not.

## Common commands

```bash
# Quality checks
pytest -q
python -m compileall -q src scripts
node --check src/atlas/web/static/app.js

# Discover and ingest an approved source
atlas ingest discover --domain example.com --seed-url https://example.com

# Inspect operations and search quality
atlas ops dry-run --json
atlas search programs --query "bench"
atlas search evaluate --fixture docs/engineering/search-eval-fixture.json
```

Run `atlas --help` for the full operator command surface. Crawl operations are
intentional and domain-policy controlled; run a dry-run before a production
batch.

## Production

The supported deployment is one Docker service on Google Cloud Run, backed by
Supabase and a private Google Cloud Storage model archive. It is configured for
one vCPU, 1 GiB memory, zero minimum instances, a maximum of one instance, and
one concurrent request. This bounds spend and keeps the in-memory rate limiter
coherent; the tradeoff is a cold start after inactivity.

Use the [production deployment guide](docs/operations/production-deployment.md)
for release configuration, migrations, model artifact handling, smoke tests,
monitoring, and rollback. `scripts/deploy_cloud_run.sh` is the supported
release path.

## Security and reliability

- Supabase JWT verification via JWKS on authenticated routes
- Five-request lifetime Ask quota by default, plus IP and user rate limits
- Explicit trusted hosts, HTTPS redirect in production, CORS allowlist, body
  size limits, CSP, HSTS, and safe DOM rendering
- Immutable, checksummed model artifacts fetched using the Cloud Run runtime
  identity; no model or service credential is committed to Git
- Reranker failures preserve baseline order instead of failing a search

See [SECURITY.md](SECURITY.md) for reporting and development requirements, and
the [operations runbook](docs/operations/ops-runbook.md) for incident response.

## Repository map

```text
src/atlas/api/          HTTP service, auth, quotas, security, and web routes
src/atlas/cli/          Operator CLI commands
src/atlas/ingest/       Discovery, extraction, normalization, and refresh logic
src/atlas/search/       Structured and full-text retrieval
src/atlas/ml/           Dataset, training, evaluation, and reranker serving
src/atlas/ops/          Admission, policies, planning, execution, and metrics
docs/                   Maintained product, architecture, engineering, and ops docs
configs/                Model and Cloud Run configuration examples
scripts/                Model artifact and Cloud Run release tooling
tests/                  Unit, contract, and integration-style tests
```
