# Corpus expansion v1

## Objective

Increase program and training-knowledge coverage across distinct training
contexts while preserving source provenance, crawl controls, and extraction
quality. This is an ingestion campaign, not a claim that every source produces
a structured program record.

## Source tracks

| Track | Domains | Intended coverage |
|---|---|---|
| Powerlifting and coaching | Barbell Medicine, Stronger By Science, PowerliftingToWin | competition preparation, strength, powerbuilding, novice/intermediate programming |
| Novice barbell strength | Starting Strength | linear progression, novice/intermediate transition, three-day programs |
| Hypertrophy programming | RP Strength | volume landmarks, muscle-specific hypertrophy, specialization concepts |
| Olympic lifting and conditioning | California Strength | Olympic weightlifting, squat specialization, general fitness, work capacity |

## Controlled waves

1. **Wave 1:** discover four new domains with a 20-candidate discovery cap,
   then extract no more than four sources per new domain and eight established
   Barbell Medicine pending sources.
2. **Checkpoint:** inspect success rate, parse confidence, program count,
   source-type mix, failure codes, cost, and topic coverage. Pause any domain
   with unreliable extraction or poor program yield.
3. **Wave 2:** extract up to six candidates from each healthy, program-focused
   new-domain queue. Hold existing Barbell Medicine product pages and any
   discovered intake/form/utility URLs for targeted review rather than treating
   the pending queue as automatically in scope.
4. **Checkpoint:** refresh corpus metrics and run representative retrieval
   queries. Identify remaining zero-result categories before adding more
   domains.

No medical-treatment claims are used as advice, and public source content is
kept provenance-linked rather than republished as a substitute for the source.
