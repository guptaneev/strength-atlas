# Production deployment

Strength Atlas runs as one Google Cloud Run service in `us-central1`, backed by
Supabase and a private Google Cloud Storage model archive. Cloud Run serves both
the API and `/app`; there is no second hosting provider or legacy deployment
path to maintain.

## Production contract

- Service: `strength-atlas`
- Region: `us-central1`
- Runtime identity: `strength-atlas-runtime@<project>.iam.gserviceaccount.com`
- Resources: 1 vCPU, 1 GiB memory, zero minimum instances, one maximum
  instance, concurrency one, 60-second request timeout
- Secrets: database URL, Supabase service key, and Browser Use API key live in
  Secret Manager
- Model: an immutable, checksummed archive in private GCS; no model or service
  key is committed to the repository

The one-instance limit bounds cost and keeps process-local rate limiting
coherent. It also means the service can cold-start after idle time; model
activation may make the first ranked request slower. Reranking fails open to
baseline order if loading or inference cannot finish within its configured
window.

## Release prerequisites

1. Link billing and enable Cloud Run, Cloud Build, Artifact Registry, Secret
   Manager, and Cloud Storage in the target project.
2. Create the runtime service account and grant it read access to the private
   model bucket.
3. Create these Secret Manager secrets:
   - `atlas-database-url`
   - `atlas-supabase-service-key`
   - `atlas-browser-use-api-key`
4. Copy `configs/cloud-run.env.example.yaml` to
   `var/atlas/cloud-run.env.yaml` and replace every placeholder. Keep secret
   values out of the file.
5. Package and upload the model artifact with `scripts/model_artifact.py`; set
   its URL and checksums in the environment file.

## Deploy

From a clean worktree:

```bash
scripts/deploy_cloud_run.sh <project-id> us-central1 var/atlas/cloud-run.env.yaml
```

The script builds a commit-tagged image, runs Alembic through the Cloud Run
migration job, deploys the service with the cost limits above, pins the CORS
origin and trusted host to the service URL, and restores public invocation.

## Required smoke checks

Run these against the deployed service URL without consuming an Ask quota:

```bash
curl --fail-with-body <service-url>/health
curl --fail-with-body <service-url>/ready
curl --fail-with-body '<service-url>/search/programs?query=bench&limit=3'
curl --fail-with-body <service-url>/retrieval/status
```

Expect health and readiness to return `200`, program search to return source
metadata, and the status endpoint to report `mode: reranked` and
`model_loaded: true` after a ranked search. Also check `/app` in a browser,
sign in with a test account, and verify a single Ask response, quota update,
and evidence cards.

## Monitoring and rollback

Monitor Cloud Run readiness, 5xx/504 responses, authentication errors, quota
and rate-limit events, model-load failures, and `reranker_fallback` frequency.
Investigate recurring fallback events or a sustained fallback rate above 5%.

To roll back application behavior, route traffic to the last verified Cloud Run
revision and repeat the smoke checks. Prefer a forward database fix unless a
tested, data-safe Alembic downgrade is available. To disable the model quickly,
remove its archive URL and checksum from the release environment and redeploy;
baseline retrieval remains available.
