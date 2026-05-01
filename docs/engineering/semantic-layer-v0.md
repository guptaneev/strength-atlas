# Semantic Layer V0 (Non-Disruptive Hook Plan)

This V0 plan introduces semantic-ingestion hook contracts only. It does not add embeddings, vector indexes, or Ask runtime execution in the CLI MVP.

Current state:

- Search remains Postgres full-text + structured filters.
- Browser Use remains acquisition/extraction only.

V0 hook contract:

- `EmbeddingHookPayload` and `EmbeddingHookResult` in [`src/atlas/ask/contracts.py`](../../src/atlas/ask/contracts.py)

Intended integration point:

- After a `Document` is persisted in extraction flow, a future background worker can consume the hook payload and write semantic artifacts to a dedicated store.

Compatibility constraints:

- No schema migration required for this scaffold.
- Existing CLI commands and output contracts remain stable.
