# Answer-model staging service

The repository now includes a standalone GPU inference service for the trained
Qwen2.5-3B LoRA adapter.

## Contract

- `POST /v1/generate` accepts a query, retrieved evidence, requested model
  version, and adapter checksum.
- The service rejects API-key, version, and checksum mismatches.
- It rejects empty answers, missing citations, and citations outside the
  supplied evidence set.
- The main Strength Atlas API still owns the deterministic fallback and keeps
  the answer model disabled unless its feature flag is enabled.

## Container and deployment

`Dockerfile.answer-model` builds the CUDA runtime. The deployment script mounts
the private adapter from a read-only Cloud Storage bucket and deploys a private
Cloud Run service with one NVIDIA L4, four CPUs, 16 GiB memory, concurrency one,
and a Secret Manager API key.

```bash
scripts/deploy_answer_model_cloud_run.sh \
  PROJECT_ID us-central1 ADAPTER_BUCKET path/to/adapter \
  dpo-qwen25-3b-v1 ARTIFACT_SHA256
```

The script intentionally refuses to deploy with an uncommitted worktree, no
active gcloud identity, a missing adapter bucket, a missing API-key secret, or
an invalid checksum.

## Benchmark

After deployment, create a request payload containing non-sensitive evidence
and run:

```bash
python scripts/benchmark_answer_server.py \
  --url https://STAGING_URL/v1/generate \
  --payload var/atlas/answer-benchmark-request.json \
  --api-key "$ATLAS_ANSWER_SERVER_API_KEY" \
  --output var/atlas/answer-server-gpu-benchmark.json
```

The report records p50, p99, mean latency, sequential throughput, and success
rate. Do not set the production feature flag until the staging report is
reviewed.
