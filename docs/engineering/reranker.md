# Strength Atlas reranker

This is the single durable reference for the learned ranking system.

## What it ranks

One cross-encoder handles two typed candidate collections:

- `program`: structured program recommendations rendered with program metadata
  and source context.
- `source_evidence`: source-backed informational evidence rendered with title,
  type, author, canonical URL, and extracted text.

The lexical/structured retrievers generate candidates. The cross-encoder reads
the query and each candidate together, scores up to 50 candidates within the
appropriate collection, and returns the requested top results. Program and
evidence metrics remain separate in serious evaluation even though one model
can score both representations.

## Model artifact

- Name: `strength-atlas-cross-encoder-authoritative-v1`
- Base checkpoint: `cross-encoder/ms-marco-MiniLM-L6-v2`
- Local path: `var/atlas/models/strength-atlas-cross-encoder-authoritative-v1`
- Weights SHA-256: `cfaabc87dd4da2567d1d4ad8ac61398c9d45a0653d671362a24d52c57a200da7`
- Release manifest: [`configs/reranker-v1-release.json`](../../configs/reranker-v1-release.json)
- Input length: 256 tokens
- Training: two epochs, batch size 16, AdamW, learning rate `2e-5`, seed 42
- Training pairs: 823, including four extra copies of each human-authoritative pair
- Validation pairs: 167 across seven held-out queries
- Test pairs: 114 across six held-out queries

Held-out bootstrap benchmark:

| Metric | Existing retrieval order | Fine-tuned reranker | Change |
|---|---:|---:|---:|
| nDCG@10 | 0.5619 | 0.8455 | +0.2836 |
| MRR | 0.9167 | 0.9167 | +0.0000 |

The model gives extra training weight to the 25 product-owner judgments for
the beginner four-day powerlifting query. Those judgments are authoritative for
that query. All remaining bootstrap grades are teacher-distilled supporting
data, not claimed as human relevance truth. The artifact's `training-report.json`
records this distinction, exact splits, pair counts, parameters, and results.

## Reproduce the pipeline

Candidate pooling, review export, teacher bootstrap, training, splits, baseline
metrics, and error-analysis commands live under `atlas ml`. The checked-in
configuration is `configs/reranker-v1.yaml`.

Generate program or evidence pools:

```text
atlas ml build-pools --dataset <queries.json> --output <draft.json> --retrieval-depth 20 --random-negatives 5 --seed 42
atlas ml export-review --dataset <draft.json> --output <review.json>
```

Create bootstrap labels and train:

```text
atlas ml bootstrap-label --dataset <draft.json> --review <review.json> --output <bootstrap.json>
atlas ml train --program-dataset <program-bootstrap.json> --program-review <program-review.json> --evidence-dataset <evidence-bootstrap.json> --evidence-review <evidence-review.json> --human-judgments docs/engineering/ml/human-judgments-v1.json --output-dir var/atlas/models/strength-atlas-cross-encoder-authoritative-v1
```

For a human benchmark, replace the bootstrap files with completely judged
datasets using the same 0–3 scale. Freeze them before splitting or evaluation.

## Experiment tracking

Every new training run can record its configuration, query and pair counts,
per-epoch mean loss, held-out validation and test metrics, and the generated
`training-report.json` as a Weights & Biases artifact. The corpus, review
sheets, human judgments, and model weights are deliberately not uploaded.

Install the opt-in dependency and authenticate only on the training machine:

```text
pip install -e ".[experiment]"
wandb login
atlas ml train ... --wandb-project strength-atlas --wandb-mode online --wandb-run-name cross-encoder-v2
```

Use `--wandb-mode offline` to create a local, later-syncable run without making
a network request. Tracking defaults to `disabled`; the production serving
image has no W&B dependency. `WANDB_PROJECT`, `WANDB_ENTITY`, and `WANDB_MODE`
are supported as environment variables for automated training jobs.

When comparing a new model against the released benchmark, preserve the
historical holdout with
`--fixed-evaluation-splits configs/reranker-v1-fixed-evaluation-splits.json`.
Additional reviewed program data can be supplied through
`--additional-program-dataset` and `--additional-program-review`; those query
sets become training-only so they cannot leak into the fixed evaluation sets.
Each evaluation report retains its query-level scores and reports a 95%
query-bootstrap interval for nDCG@10 using 1,000 resamples by default.

## Serving

Production uses the private release archive to populate
`ATLAS_RERANKER_MODEL_PATH` at startup. The API retrieves up to
`ATLAS_RERANKER_CANDIDATE_DEPTH` candidates, reranks programs and source
evidence with the same model, preserves identifiers and provenance, and
truncates to the requested result count. If the model is not configured, the
existing retrieval order remains unchanged.

Model loading and scoring run on a cached, bounded worker pool. Load errors,
bad artifacts, checksum mismatches, incompatible models, inference errors,
timeouts, and worker saturation return the unchanged baseline order. Production
uses an eight-second reranker timeout, so a slow cold load can return a safe
baseline response before later requests use the loaded model. The candidate
depth, requested top-k, batch size, input length, worker count, timeout, and
failure cooldown are independently configurable and bounded.

The service logs a `reranker_completed` event with model version, candidate
count, and model-attempt latency in milliseconds. This timing starts when work
is submitted to the reranker worker and includes lazy model loading, so the
first request after a cold start is intentionally comparable with later warm
requests. `GET /retrieval/status` exposes the latest completed attempt's
latency and candidate count, and retrieval debug summaries expose separate
source and program reranker timings. Fallbacks are represented explicitly and
must not be interpreted as successful reranker latency measurements.

## Benchmarking

Use `scripts/benchmark_reranker.py` to measure a warmed 50-candidate workload.
It reports p50/p99 latency, throughput, fixed-test nDCG@10, and CPU dynamic
int8 results when the installed PyTorch backend supports quantized linear
operators. Run it with `--device cuda` on a CUDA-capable runner to produce GPU
numbers; do not compare a CPU and GPU result from different model artifacts or
candidate counts. The report also includes Recall@3, which has more headroom
than MRR for this corpus.

The release artifact workflow, activation checks, and rollback procedure are in
[the production deployment guide](../operations/production-deployment.md).

The stable Python boundary is `FineTunedCrossEncoder` plus typed
`RerankCandidate` objects. Replacing the model does not require changing the
search or Ask Atlas contracts.
