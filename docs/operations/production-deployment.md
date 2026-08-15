# Production deployment: Cloud Run + Supabase

This is the canonical release guide for Strength Atlas. Google Cloud Run runs one Docker service that serves the API and frontend. Supabase continues to provide Postgres, Auth, and private model storage. The existing Vercel deployment is a baseline preview; `render.yaml` is retained only as a disabled legacy alternative.

The Cloud Run service uses request-based billing with 1 vCPU, 1 GiB RAM, zero minimum instances, one maximum instance, and concurrency one. This fits the measured model peak of approximately 608 MiB, scales to zero when unused, bounds the maximum spend rate, and keeps the process-local rate limiter coherent. The tradeoff is a cold start after inactivity. See the official [Cloud Run pricing](https://cloud.google.com/run/pricing), [memory configuration](https://cloud.google.com/run/docs/configuring/services/memory-limits), and [service configuration](https://cloud.google.com/run/docs/configuring) documentation.

The image pins CPU-only PyTorch 2.7.1, excludes development-only packages, and runs as the unprivileged `atlas` user. The model cache is ephemeral and is securely rebuilt from the immutable private archive whenever Cloud Run creates a new instance.

## One-time Google Cloud setup

You need a Google Cloud project with billing enabled. Billing is required even when usage remains inside the free allowance. Use `us-central1` to match the free-tier reference pricing unless the Supabase project is far enough away that another region materially improves latency.

Install and initialize the Google Cloud CLI, then select the project:

```bash
gcloud auth login
gcloud config set project <project-id>
```

Create a dedicated runtime identity:

```bash
gcloud iam service-accounts create strength-atlas-runtime \
  --display-name="Strength Atlas Cloud Run runtime"
```

Create these three Google Secret Manager secrets. Add their values in the Google Cloud Console so the values do not enter shell history:

- `atlas-database-url`
- `atlas-supabase-service-key`
- `atlas-browser-use-api-key`

For `atlas-database-url`, use a SQLAlchemy DSN beginning with `postgresql+psycopg://`. Cloud Run environments commonly need an IPv4-compatible Supabase endpoint. Get the Session pooler connection from Supabase's **Connect** panel and use port `5432`. Supabase documents Session mode as the persistent-backend option for IPv4-only networks.

Grant the runtime identity access to only those secrets:

```bash
for secret in atlas-database-url atlas-supabase-service-key atlas-browser-use-api-key; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:strength-atlas-runtime@<project-id>.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

The deployer also needs permission to build images, deploy Cloud Run services and jobs, act as the runtime identity, and read the referenced secrets. A project owner normally has enough access for the first personal deployment; use narrower IAM roles for additional deployers.

## Release environment

Copy the tracked non-secret template into the ignored `var/` directory:

```bash
cp configs/cloud-run.env.example.yaml var/atlas/cloud-run.env.yaml
```

Replace `REPLACE_PROJECT_REF` and `REPLACE_PUBLISHABLE_KEY`. Do not put the database password, Supabase service key, Browser Use key, or model-storage credential in this file. The deployment script maps Secret Manager values into the container at runtime.

The script initially deploys a private revision with an invalid bootstrap hostname. It reads Google's generated HTTPS URL, updates CORS and trusted-host configuration to that exact hostname, and only then grants public access. This avoids a wildcard-host bootstrap window.

## Package and publish the model

The model stays outside ordinary Git as an immutable, versioned `.tar.gz` artifact.

Package the verified local model:

```bash
python scripts/model_artifact.py package \
  --source var/atlas/models/strength-atlas-cross-encoder-authoritative-v1 \
  --output dist/strength-atlas-cross-encoder-authoritative-v1.tar.gz \
  --version strength-atlas-cross-encoder-authoritative-v1
```

The emitted values must match [the tracked release manifest](../../configs/reranker-v1-release.json):

- archive SHA-256: `18e9a27e5eb67e72b43c88ec81d25c25f5e3c9252e183c9d0232ca3e8ace2657`
- weights SHA-256: `cfaabc87dd4da2567d1d4ad8ac61398c9d45a0653d671362a24d52c57a200da7`

In Supabase Storage, create a private bucket named `atlas-models` and upload the archive with this exact immutable object name:

```text
strength-atlas-cross-encoder-authoritative-v1.tar.gz
```

The authenticated object URL has this form:

```text
https://<project-ref>.supabase.co/storage/v1/object/authenticated/atlas-models/strength-atlas-cross-encoder-authoritative-v1.tar.gz
```

The deploy script exposes the existing Supabase service-key secret as the download authorization token and API key. Never place that key in the URL or tracked environment file.

At startup, the container caps download size, validates the archive checksum, rejects links and path traversal, extracts atomically, validates the weights checksum, and falls back to baseline retrieval if activation fails.

## Build, migrate, and deploy

Deploy only from a tested release commit. The script intentionally refuses an uncommitted worktree.

Run the release checks:

```bash
python -m pytest -q
python -m compileall -q src scripts
node --check src/atlas/web/static/app.js
docker build -t strength-atlas:release .
```

For the first deployment, leave `ATLAS_RERANKER_MODEL_URL` and `ATLAS_RERANKER_ARCHIVE_SHA256` commented out in `var/atlas/cloud-run.env.yaml`. Deploy the baseline:

```bash
scripts/deploy_cloud_run.sh <project-id>
```

The script performs these steps in order:

1. Enables Cloud Run, Cloud Build, Artifact Registry, and Secret Manager APIs.
2. Creates the regional Docker repository if it does not exist.
3. Builds the checked-in Dockerfile and tags the image with the Git commit.
4. Deploys and waits for the `strength-atlas-migrate` Cloud Run Job to run `alembic upgrade head`.
5. Deploys `strength-atlas` privately with 1 GiB RAM, scale-to-zero, one maximum instance, and concurrency one.
6. Pins CORS and trusted hosts to the generated service hostname.
7. Grants public invocation and prints the service URL.

Do not combine a destructive or data-rewriting migration with an application behavior release. If the migration job fails, the script stops before updating the service.

## Baseline smoke test

Run these against the printed service URL:

1. `GET /health` returns `200` and `{"status":"ok"}`.
2. `GET /ready` returns `200`; database and Supabase Auth readiness are healthy.
3. `GET /retrieval/status` returns `mode: baseline`.
4. `/app` loads with Program Discovery selected at desktop and mobile widths.
5. Program search returns no more than the requested limit and every result retains a canonical source URL.
6. Sign-in, `GET /me/quota`, one Ask request, quota consumption, rate limiting, and sign-out work with a production test account.
7. Invalid hosts, disallowed CORS origins, oversized bodies, and unauthenticated Ask requests are rejected.

## Activate reranking

After the private archive is available, add these values to `var/atlas/cloud-run.env.yaml`:

```yaml
ATLAS_RERANKER_MODEL_URL: "https://<project-ref>.supabase.co/storage/v1/object/authenticated/atlas-models/strength-atlas-cross-encoder-authoritative-v1.tar.gz"
ATLAS_RERANKER_ARCHIVE_SHA256: "18e9a27e5eb67e72b43c88ec81d25c25f5e3c9252e183c9d0232ca3e8ace2657"
```

Redeploy the same release commit:

```bash
scripts/deploy_cloud_run.sh <project-id>
```

Then verify:

1. Search for `beginner four day powerlifting`; the request succeeds and retains all program/source metadata.
2. Ask `how often should I bench`; evidence cards contain titles, domains, excerpts, dates when known, and source links.
3. `GET /retrieval/status` returns `mode: reranked`, the expected model version, and `model_loaded: true` after the first ranked request.
4. Cloud Logging contains `retrieval_mode=reranked`; a staging bad-checksum test produces `baseline_fallback` without exposing storage details or stack traces.
5. Cloud Monitoring shows memory below 1 GiB and acceptable p95 latency during representative use.

## Cost controls and monitoring

- Keep minimum instances at zero, maximum instances at one, request-based CPU throttling enabled, and concurrency at one.
- Create Google Cloud budget alerts at $1, $5, and $10. Budget alerts notify; they do not automatically cap spending.
- Configure Artifact Registry cleanup to retain only the releases needed for rollback. Source deployments and stored images have pricing separate from Cloud Run.
- Alert on sustained 5xx/504 rates, readiness failures, database/Auth failures, quota anomalies, and reranker fallback above 5% for ten minutes.
- Track p50/p95/p99 latency for program search and Ask plus the counts of `baseline`, `reranked`, and `baseline_fallback`.
- Supabase Storage downloads happen again after scale-to-zero replacement; monitor Storage egress as well as Cloud Run usage.

Never log query tokens, credentials, database messages, model paths, or response bodies.

## Rollback

- Application: route all traffic to the previously verified Cloud Run revision, then rerun baseline smoke tests. Revisions are immutable and the image tag records the release commit.
- Database: this release has no schema migration. Prefer a forward fix for future additive migrations. Use a tested Alembic downgrade only when data-safe; otherwise restore through Supabase backups/PITR and validate before repointing the app.
- Model: restore the prior version/path/URL/archive checksum/weights checksum together and redeploy. To immediately disable reranking, comment out the model URL and archive checksum and redeploy; baseline retrieval remains available.

## Production-ready acceptance criteria

Declare the release production-ready only when all of the following are true:

- CI, tests, static checks, secret scan, documentation-link audit, and an amd64 Cloud Build container build pass from the release commit.
- The Cloud Run migration job succeeds and the production database remains at Alembic head.
- Baseline and reranked program search and informational Ask pass against the production database within configured limits.
- Missing, malformed, incompatible, checksum-invalid, timed-out, and failed inference all preserve baseline order.
- IDs, URLs, provenance, source dates, metadata, and result limits survive reranking.
- Authentication, quota, rate limit, CORS, trusted hosts, HTTPS, body size, security headers, and public error sanitization pass in production.
- Desktop/mobile states and keyboard navigation are manually verified.
- Budget alerts, operational alerts, a rollback-eligible revision, and the prior model artifact are available.

If any live test, credential, object URL, monitoring integration, or approval is unavailable, record it as a blocker and do not label the release production-ready.
