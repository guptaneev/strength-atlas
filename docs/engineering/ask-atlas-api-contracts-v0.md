# Ask Atlas API Contracts (V0 Scaffold)

This document defines the initial contract surface for a future Ask Atlas retrieval/answer service without changing the current CLI-first MVP runtime.

Implemented in code:

- [`src/atlas/ask/contracts.py`](../../src/atlas/ask/contracts.py)
- [`src/atlas/api/app.py`](../../src/atlas/api/app.py) (HTTP endpoints)
- [`src/atlas/api/service.py`](../../src/atlas/api/service.py) (retrieval orchestration)

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
- Endpoints currently provide retrieval/answer plus auth/quota support:
  - `POST /auth/login` (email/password -> access token)
  - `GET /me/quota` (authenticated quota status)
  - `GET /search/sources`
  - `GET /search/programs`
  - `POST /ask/retrieve` (authenticated + quota-enforced)
  - `POST /ask/retrieve/debug` (authenticated + quota-enforced candidate/evidence diagnostics)
  - `POST /ask/answer` (authenticated + quota-enforced deterministic synthesis over retrieved evidence)
- Ask endpoints enforce a lifetime free quota (`ATLAS_ASK_LIFETIME_LIMIT`, default `5`) and return `status="quota_exceeded"` on limit breach.
- Existing CLI ingest/search behavior remains unchanged.
