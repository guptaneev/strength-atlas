# Retrieval checkpoint — corpus expansion v1

**Captured:** 2026-08-15  
**Corpus:** 133 sources, 76 documents, 306 structured programs

## Baseline checkpoint

Before the candidate-retrieval change, 8 of the 24 representative program
queries returned no results after the corpus expansion. The strict retrieval
path requires all full-text query terms to match, so natural-language
constraints such as `three-day`, `full body`, `post novice`, and `limited time`
frequently caused candidate recall failure.

The existing URL regression suite was 23/26 passing. The three failures are
the fixture's broad template and meet-prep expectations; they were present at
this checkpoint and are not used as graded relevance metrics.

## Change

`search_programs` now keeps exact full-text results first, then fills any
shortfall through `build_program_candidate_fallback_statement`.

The fallback:

- expands domain language such as novice/beginner, bodybuilding/hypertrophy,
  powerbuilding/strength/muscle, meet prep/competition/peaking, and
  full-body/upper-lower;
- infers only high-confidence structured intent (days per week, experience
  level, split type); and
- applies those inferred fields as ranking boosts rather than hard filters.

Every expansion is defined in `src/atlas/search/query_expansion.py`; there is
no opaque learned model in this stage.

## Measured effect

| Measure | Before | After |
|---|---:|---:|
| Representative queries | 24 | 24 |
| Queries with zero candidates | 8 | 0 |
| Zero-result rate | 33.3% | 0.0% |
| Candidate depth requested | 10 | 10 |

The change improves **candidate recall**, not validated ranking quality. Some
fallback top results are only broadly related to the query. This is expected:
the immediate objective is to give the later reranker a viable candidate set.

## Next validation

1. Build and human-label pools from the improved candidate sets.
2. Freeze query splits and compute baseline nDCG@10, MRR, Recall@10, and
   Precision@10.
3. Add a real embedding/vector candidate provider to the same candidate-union
   boundary only after the above lexical baseline is frozen.
4. Introduce the cross-encoder reranker after candidate recall and labels are
   stable.
