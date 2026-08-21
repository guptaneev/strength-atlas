# Evidence-grounded preference training

This is the planned answer-model experiment. It is deliberately separate from
the production reranker: the live service continues to retrieve evidence and
uses its deterministic answer formatter unless an answer-model feature flag is
enabled.

## Dataset contract

Each pair includes one user query, the exact retrieved evidence, and a chosen
and rejected answer. Answers may cite only evidence included in that pair.
`label_source` is either `human` or `model_assisted`; these populations are
never combined in headline evaluation.

Validate the file before a training run:

```bash
atlas ml preference-summary --dataset docs/engineering/ml/answer-preferences-v1.json --json
```

Target composition is roughly 2,000 pairs, with 200 human pairs. Split by
`query_id`, not by individual pairs, before training so a query never appears
in more than one split.

Create the temporary-GPU input locally from the indexed corpus. The export
contains only retrieved claim text plus matching retrieved-program metadata and
their public source URLs, never database
credentials or a database dump. It also excludes claims with no lexical overlap
with the query; a query without sufficiently relevant retrieved claims must be
recorded as insufficient evidence, not forced into a preference pair:

```bash
atlas ml export-answer-evidence \
  --dataset docs/engineering/ml/queries.json \
  --output var/atlas/answer-evidence-v1.json
```

## Free-GPU run

Use a Kaggle GPU notebook for candidate generation and a LoRA/QLoRA training
run. Do not upload the production database, secrets, or user data. Export only
the versioned preference JSON, code, configuration, and a checksummed model
artifact. Log aggregate metrics, configuration, losses, reward margins, KL,
and artifact checksum to W&B; do not upload raw human-label data.

Run both experiments on identical query-level splits:

1. Supervised fine-tuning using chosen answers.
2. LoRA + DPO using the chosen/rejected pairs.

Evaluate human-labelled pairs separately for groundedness, citation accuracy,
human preference versus the base model, answer length, and the share of cited
claims that were retrieved. Report model-assisted results only as a secondary
diagnostic.

The repository includes a deterministic contract-level evaluator for exported
generation records. It checks that every citation refers to retrieved evidence,
keeps human and model-assisted populations separate, and reports verbosity
relative to a reference answer when one is supplied:

```bash
atlas ml answer-evaluate \
  --records var/atlas/generated-answer-eval.json \
  --output var/atlas/generated-answer-report.json
```

Each record may also include `model` and `query_id`. When present, the report
adds a `by_model` section so base, SFT, and each DPO seed can be compared from
the same held-out query file without mixing their results.

The latest Kaggle held-out run generated 25 answers: five query-level test
queries evaluated with the base model, SFT seed 42, and DPO seeds 42–44. Every
generated citation referred to supplied evidence. DPO cited evidence on 100%
of answers versus 60% for the base and SFT outputs, and DPO answers averaged
23.8 words versus 32.4 for base/SFT. These are mechanical citation and
verbosity checks, not semantic groundedness scores, so blind human review is
still required. Aggregate reports are under
`docs/engineering/ml/answer-training-kaggle-v1/`; raw records and the review
packet remain local or in the private run artifact.

An earlier, non-blinded product review approved `first_meet`, `bodybuilding_intermediate`,
`powerbuilding`, and `full_body_3_day`. The original
`advanced_powerlifting` answer was rejected, then corrected with the
specialization-aware retrieval boost and approved by the reviewer. The full
judgment history is recorded in
`docs/engineering/ml/heldout-human-review-v1.json`.

That earlier review does not satisfy the current release gate because one
query-level decision was applied to all model outputs. Use
`blind-human-review-packet.json` for a candidate-level comparison; keep the
separate model key under `var/atlas/` closed until judgments are finalized.

Apply those judgments to generated records with:

```bash
atlas ml answer-review-summary \
  --records var/atlas/generated-answer-eval.json \
  --review docs/engineering/ml/heldout-human-review-v1.json \
  --output var/atlas/human-review-report.json
```

The review report also includes a 1,000-iteration query-level bootstrap 95%
confidence interval for approval rate, avoiding pseudo-replication from the
four model records generated for each query.

The retrieval fallback now applies a soft specialization boost for
powerlifting queries, prioritizing programs tagged `powerlifting` or `strength`
over adjacent CrossFit/general-fitness programs while preserving candidate
recall. This specifically addresses the rejected advanced-powerlifting case.

For a repeatable GPU run, use the notebook-independent generator. It de-duplicates
the test split by query and emits records for the base model plus each adapter:

```bash
pip install -U \
  'transformers>=4.51,<5' 'peft>=0.15,<1' 'accelerate>=1.4,<2' \
  'huggingface-hub>=0.34,<1'

python scripts/evaluate_answer_models.py \
  --test-split docs/engineering/ml/answer-preferences-human-v8-test.json \
  --adapter dpo-seed42=/kaggle/working/dpo-lora-seed42-cached-ref \
  --adapter dpo-seed43=/kaggle/working/dpo-lora-seed43-cached-ref \
  --adapter dpo-seed44=/kaggle/working/dpo-lora-seed44-cached-ref \
  --output /kaggle/working/generated-answer-eval.json
```

`citation_format_valid_rate` and `citation_precision` validate the citation
contract; they are not semantic entailment scores. Semantic groundedness still
requires a human or model-assisted review of whether the cited claim actually
supports the answer.

## Release gate

An answer model is released only as a versioned, checksummed artifact behind a
feature flag. If it cannot load, times out, or violates the citation contract,
the service falls back to the current deterministic evidence response and logs
the serving model/version for the request.
