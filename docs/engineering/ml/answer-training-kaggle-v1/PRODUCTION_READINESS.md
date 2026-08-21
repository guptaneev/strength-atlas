# Production-readiness decision

**Decision: not production ready. Keep this work on a feature branch.**

## Passed

- Query-disjoint human preference train/test split
- Qwen2.5-3B LoRA SFT run and three DPO seed runs completed
- Versioned adapter checksums recorded
- Mechanical citation-contract and verbosity evaluation completed
- Blind candidate-level review packet generated
- Feature-flagged serving client validates version, checksum, and citations
- Deterministic fallback remains the default on timeout or validation failure
- Local automated test suite passes

## Blocking release gates

1. The 25 generated answers have not received candidate-level blind human
   judgments. The earlier query-level product review is not sufficient.
2. The human preference core has 91 pairs, below the approximately 200-pair
   target, and the larger model-assisted dataset has not been built.
3. The answer-model HTTP endpoint has not been deployed and exercised in a
   staging environment with the serving feature flag.
4. GPU serving latency and throughput have not been benchmarked.
5. W&B logs are retained offline in the Kaggle artifact but are not synced to
   the tracked online project.

No production-quality or human-preference improvement claim should be made
until these gates are closed. The current automatic result is evidence that
DPO improved citation behavior on five held-out queries, not that it improved
overall answer quality.
