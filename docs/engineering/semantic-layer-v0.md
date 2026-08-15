# Semantic Layer V0 (Non-Disruptive Hook Plan)

This V0 plan introduces semantic-ingestion hook contracts only. It does not add embeddings, vector indexes, or Ask runtime execution in the CLI MVP.

Current state:

- Search uses exact Postgres full-text + structured filters first, then an
  intent-expanded lexical candidate fallback when exact retrieval cannot fill
  the requested result count. The fallback uses inspectable aliases and soft
  boosts for inferred days per week, experience level, and split type.
- Browser Use remains acquisition/extraction only.

The fallback is **not** vector or embedding search. It is the current
high-recall candidate leg that a future vector retriever will union with before
the cross-encoder reranks candidates.

V0 hook contract:

- `EmbeddingHookPayload` and `EmbeddingHookResult` in [`src/atlas/ask/contracts.py`](../../src/atlas/ask/contracts.py)

Intended integration point:

- After a `Document` is persisted in extraction flow, a future background worker can consume the hook payload and write semantic artifacts to a dedicated store.

Compatibility constraints:

- No schema migration required for this scaffold.
- Existing CLI commands and output contracts remain stable.
