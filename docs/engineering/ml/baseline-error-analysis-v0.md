# Baseline error analysis v0

**Status:** provisional manual analysis; not a labeled benchmark or model-selection result  
**Baseline:** `program_search_baseline` (current PostgreSQL full-text and structured program search)  
**Sample:** 24 seed queries in `docs/engineering/ml/queries.json`; top five live results inspected on 2026-08-15  
**Corpus at inspection:** 210 programs, 56 documents, 83 sources

## Important limitation

This is a qualitative error analysis against each query's documented intent. It
does not assign relevance grades and must not be used to report nDCG, MRR,
Recall, or Precision. Create, review, and freeze candidate-pool judgments
before producing those metrics.

## Findings

| Primary failure category | Queries | Share | Representative observations |
|---|---:|---:|---|
| Candidate-retrieval failure / terminology mismatch | 9 | 37.5% | `intermediate_bench`, `limited_time_3_day`, `general_strength_4_day`, `low_volume`, `high_volume_hypertrophy`, `upper_lower_4_day`, `full_body_3_day`, `post_novice`, and `bench_3_day` returned no programs. |
| Goal or lift-focus mismatch | 7 | 29.2% | First-meet, rehab, peaking, bodybuilding, deadlift-focused, deadlift-technique, and squat-specialization queries commonly retrieved generic powerlifting programs. |
| Experience-level mismatch or misranking | 3 | 12.5% | The four-day beginner query ranked an advanced program first; beginner hypertrophy returned an unqualified catalogue then powerlifting programs; intermediate Strength II ranked above an advanced Strength III result for the advanced query. |
| Explicit metadata/constraint ignored | 4 | 16.7% | Frequency, home-gym equipment, audience, and minimum-effective-dose constraints were not represented strongly enough to choose candidates that satisfy them. |
| Partially relevant result misranked | 1 | 4.2% | For `powerbuilding`, generic Strength programs ranked above the explicitly powerbuilding-labeled programs at ranks 3–4. |

Each query is assigned one primary category for this summary. Several failures
overlap; for example, the first-meet query also has an experience-level issue.

## Representative ranking evidence

- **Beginner, four-day powerlifting:** `Strength III` (advanced, four days)
  ranked first; `Powerbuilding II` (intermediate, four days) ranked second.
  The ranking preserves the activity and frequency but misses the most important
  experience constraint.
- **First powerlifting meet:** the top five results were the same generic
  powerlifting/powerbuilding family, including advanced programs. None visibly
  encodes first-meet preparation or novice suitability.
- **High-frequency squat:** a one-lift collection ranked first, which is a
  plausible candidate, but it was followed by broad program-bundle and
  newsletter-derived entries. Frequency is not available as a reliable ranking
  signal and source/page type leaks into results.
- **Advanced powerlifting:** an intermediate Strength II program outranked the
  advanced Strength III program. This is an ordering failure within an
  otherwise plausible candidate set—a strong reranker target.
- **Powerbuilding:** explicitly powerbuilding programs existed but ranked third
  and fourth behind generic Strength programs. This is another good cross-
  encoder training example because lexical overlap alone did not resolve the
  intended combined strength-and-muscle goal.
- **Rehab and peaking:** generic powerlifting results occupied the top ranks.
  No candidate visibly represented rehabilitation or pre-competition peaking.
  This is largely a corpus/recall issue, not just a ranking issue.

## Hypothesis for the reranker

When the baseline supplies a plausible candidate set, a cross-encoder using
the query plus `program_with_metadata_v1` should improve ordering for
multi-constraint queries, especially experience level, lift focus, goal, and
powerbuilding-vs-strength distinctions. The positive examples are the advanced
powerlifting and powerbuilding queries; their preferred candidate already
appears in the pool but below a weaker match.

## Required guardrails for Phase 7

1. Rerank only the top 20–50 retrieved candidates, then return the top 10.
2. Include explicit metadata in the candidate representation: experience level,
   days per week, specialization, progression type, and split type.
3. Mine hard negatives from the generic powerlifting programs that appear for
   specific intent queries such as rehab, first meet, bench specialization, and
   deadlift specialization.
4. Add diversity handling or source/page-type features: broad catalog and
   newsletter-derived entries can crowd out program-detail results.
5. Do not expect reranking to improve the 9 zero-result queries. Address their
   candidate-recall failure separately with synonym/intent expansion, less
   brittle retrieval, richer extraction, or an embedding retriever.
6. Freeze human relevance judgments before training. Use the validation split
   for model choice and keep the test split unseen until final evaluation.

## Next experiment

Build candidate pools for the 24 queries, label the top-retrieved candidates
and random negatives, and add the generic near-matches above as hard negatives.
Then rerun this analysis with measured baseline metrics and the same categories.
