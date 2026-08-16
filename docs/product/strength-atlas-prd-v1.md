# Strength Atlas product scope

## Product

Strength Atlas helps lifters and coaches make training decisions from public
coaching material without losing the source. It combines operator-managed
ingestion with program discovery, source search, and evidence-backed answers.

## Users

- Lifters comparing programs, schedules, and coaching approaches
- Coaches checking the source material behind a recommendation
- Operators maintaining a reliable, permission-respecting training corpus

## Current experience

The web app provides three surfaces:

1. **Program Discovery** searches normalized program records by a free-text
   query and optional domain filter.
2. **Ask Atlas** requires sign-in and returns a deterministic answer with
   evidence cards. Users can inspect the source title, domain, excerpt, date
   when known, and canonical link.
3. **Research Library** searches and browses indexed source material.

The operator CLI admits domains, discovers URLs, extracts documents, reviews
backlog, runs bounded batches, evaluates search, and trains or evaluates the
reranker.

## Product principles

- **Traceability over assertion.** A recommendation is only useful when its
  supporting material is visible.
- **Respectful ingestion.** Operators use explicit domain policies, bounded
  batches, retries, and review rather than indiscriminate crawling.
- **Grounded output.** Ask Atlas reports insufficient evidence instead of
  manufacturing a conclusion.
- **Operational restraint.** Authenticated Ask requests are quota and
  rate-limited; the production service has a bounded scale configuration.

## Functional boundaries

Implemented now:

- Browser Use-backed discovery and extraction for approved domains
- Normalized sources, documents, programs, claims, and crawl history
- Structured and full-text retrieval with optional learned reranking
- Supabase authentication, lifetime Ask quotas, and rate limiting
- Source-linked evidence cards and source browsing

Not implemented:

- Personalized training prescriptions
- Automatic recurring crawls without operator approval
- A generative model that writes advice beyond the retrieved corpus
- Billing, paid accounts, or automated quota upgrades
- Vector retrieval or user-owned source integrations

## Success criteria

The product is healthy when an operator can maintain the corpus predictably,
users can find programs and inspect sources, and every Ask response remains
bounded by the available evidence. Reliability, provenance, and safe failure
matter more than unsupported answer fluency.
