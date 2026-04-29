# Ask Atlas API Contracts (V0 Scaffold)

This document defines the initial contract surface for a future Ask Atlas retrieval/answer service without changing the current CLI-first MVP runtime.

Implemented in code:

- [`src/atlas/ask/contracts.py`](/Users/neevgupta/browser-use-project/src/atlas/ask/contracts.py)

Core request/response contracts:

- `RetrievalRequest`
- `RetrievalFilters`
- `EvidenceCard`
- `AskAtlasResponse`

Semantic hook contracts:

- `EmbeddingHookPayload`
- `EmbeddingHookResult`

Design notes:

- Contracts are intentionally API-first and backend-facing.
- No web UI or ask runtime is introduced by this scaffold.
- Existing CLI ingest/search behavior remains unchanged.
