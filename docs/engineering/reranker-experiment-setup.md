# Reranker experiment setup (Phases 0–6 complete)

Strength Atlas retrieves **programs**. The canonical model input is
`program_with_metadata_v1`: program name and summary, structured program fields,
source title/URL, and extracted source text. `atlas.ml.documents.program_document_text`
is the sole renderer; use it for labeling exports, training, and inference.

The experiment tests whether a learned cross-encoder improves the current
program-search baseline. Primary metric: nDCG@10. Secondary metrics: MRR,
Recall@10, and Precision@10. The present application implements PostgreSQL
full-text/structured retrieval rather than cosine similarity, so reports call
the baseline `program_search_baseline` honestly. If an embedding retriever is
introduced, add it as a separately named baseline; do not overwrite results.

## Dataset lifecycle

1. Start a JSON dataset containing realistic, query-level intents and an empty
   `candidates` array. Use relevance grades 0–3 defined in the dataset output.
2. Create pools from the current retriever plus reproducible random negatives.
   The retriever candidates are the initial hard-negative mining set: they are
   already lexically or structurally close to the query, but labels determine
   whether each is a positive or a hard negative:

   `atlas ml build-pools --dataset docs/engineering/ml/queries.json --output docs/engineering/ml/candidate-pools-draft.json`

3. Human-review every candidate, add its grade and a short reason, then change
   `status` to `frozen`. Treat this file as immutable after the split.
4. Split by query—not query/candidate pair:

   `atlas ml split --dataset docs/engineering/ml/candidate-pools-frozen.json --output docs/engineering/ml/splits-v1.json --seed 42`

5. Establish the frozen baseline and retain the per-query report:

   `atlas ml baseline --dataset docs/engineering/ml/candidate-pools-frozen.json --output var/atlas/ml/baseline-v1.json`

6. Produce a review sheet, classify 20–30 representative failures, and save its
   summary with the experiment:

   `atlas ml error-template --baseline-report var/atlas/ml/baseline-v1.json --output docs/engineering/ml/baseline-errors-v1.json`

The baseline command refuses drafts and incomplete labels. This prevents
accidentally treating provisional labels as a model-selection benchmark.

## Phase 7 handoff

`configs/reranker-v1.yaml` records the initial cross-encoder experiment values.
The `Reranker` protocol and `rerank_candidates` helper are the inference seam:
the Phase 7 fine-tuned model needs only to score each query/program-text pair
and return one score per candidate. It should rerank the top 50 baseline
candidates and return the best 10, without changing candidate retrieval.
