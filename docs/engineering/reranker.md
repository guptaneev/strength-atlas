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

The release artifact workflow, activation checks, and rollback procedure are in
[the production deployment guide](../operations/production-deployment.md).

The stable Python boundary is `FineTunedCrossEncoder` plus typed
`RerankCandidate` objects. Replacing the model does not require changing the
search or Ask Atlas contracts.
