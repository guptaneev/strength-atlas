# Ask Atlas API Contracts (V0 Scaffold)

This document defines the initial contract surface for a future Ask Atlas retrieval/answer service without changing the current CLI-first MVP runtime.

Implemented in code:

- [`src/atlas/ask/contracts.py`](/Users/neevgupta/browser-use-project/src/atlas/ask/contracts.py)
- [`src/atlas/api/app.py`](/Users/neevgupta/browser-use-project/src/atlas/api/app.py) (HTTP endpoints)
- [`src/atlas/api/service.py`](/Users/neevgupta/browser-use-project/src/atlas/api/service.py) (retrieval orchestration)

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
- Endpoints currently provide retrieval and evidence payloads only:
  - `GET /search/sources`
  - `GET /search/programs`
  - `POST /ask/retrieve`
  - `POST /ask/retrieve/debug` (candidate/evidence diagnostics)
  - `POST /ask/answer` (deterministic synthesis over retrieved evidence)
- Existing CLI ingest/search behavior remains unchanged.
