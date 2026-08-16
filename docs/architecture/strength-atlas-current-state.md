# Strength Atlas architecture

## Runtime topology

One Google Cloud Run service serves the FastAPI API and static web app. The
service connects to Supabase for Postgres, Auth, and crawl-artifact storage.
The learned reranker is packaged as an immutable archive in private Google
Cloud Storage and is fetched with the Cloud Run runtime identity.

```text
Web app / operator CLI
        │
        ▼
FastAPI service ── Supabase Auth
        │          Supabase Postgres
        │          Supabase Storage
        ▼
Retrieval + reranker ── private Google Cloud Storage model archive
        ▲
Browser Use ingestion (operator-triggered)
```

## Ingestion and data flow

1. A domain policy admits a source domain and constrains discovery and crawl
   behavior.
2. Browser Use discovers eligible URLs and extracts structured content from a
   source page.
3. Validation and normalization persist `sources`, `documents`, `programs`,
   `claims`, and `crawl_jobs`.
4. Operators review backlog, quality, policy decisions, and metrics before
   additional work.

Raw source artifacts live in Supabase Storage. Postgres stores the structured
records and the provenance needed to reconstruct a result.

## Retrieval and Ask Atlas

Program and source retrieval use structured filters plus Postgres full-text
search. When configured, the cross-encoder receives bounded candidate sets and
reranks them without changing IDs, URLs, or source metadata. A model load,
artifact, inference, timeout, or capacity failure leaves the baseline ordering
in place.

Ask Atlas retrieves evidence and builds a deterministic answer from that
evidence. It is intentionally not a free-form language-model completion path.
The endpoint requires Supabase-backed authentication, consumes a lifetime
quota, and is limited by both client IP and user identity.

## Public surfaces

- `/app` — web app
- `/health` — liveness check
- `/ready` — database and auth readiness check
- `/retrieval/status` — reranker configuration and load state
- `/search/programs`, `/search/sources`, and `/sources` — public discovery
- `/ask/*` and `/me/quota` — authenticated, quota-protected services

The CLI is the operator interface. See `atlas --help` for commands and the
domain policy example for crawl guardrails.

## Security and reliability boundaries

- Production requires explicit HTTPS CORS origins and trusted hosts.
- Security middleware adds CSP, HSTS, frame denial, no-sniff, referrer, and
  permissions policies; request bodies are bounded.
- The service uses one maximum Cloud Run instance and concurrency one so the
  process-local rate limiter remains coherent and spend stays bounded.
- The model archive has archive and weights checksums. Extraction rejects links
  and path traversal before atomically activating the artifact.
- Search and Ask preserve baseline retrieval order when reranking cannot finish
  safely.

## Maintainer guidance

Keep this document aligned with deployed behavior. Put operational procedures
in the operations documents and model-specific details in the reranker guide.
