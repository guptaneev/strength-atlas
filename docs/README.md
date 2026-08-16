# Strength Atlas documentation

The documents below describe the current system. Historical deployment paths,
SDK snapshots, and superseded implementation plans are intentionally not kept
in the repository.

## Product and architecture

- [Product scope](product/strength-atlas-prd-v1.md) — users, goals, boundaries,
  and current product behavior.
- [Current architecture](architecture/strength-atlas-current-state.md) — runtime
  components, data flow, interfaces, and reliability boundaries.

## Engineering

- [Reranker](engineering/reranker.md) — model release, evaluation, reproduction,
  and serving behavior.
- [Search evaluation fixture](engineering/search-eval-fixture.json) — regression
  inputs for CLI search evaluation.
- [Domain crawl policy example](engineering/domain-crawl-policies.example.json)
  — allowlist and per-domain crawl controls.

## Operations

- [Production deployment](operations/production-deployment.md) — Cloud Run,
  Supabase, private model storage, release steps, and rollback.
- [Operations runbook](operations/ops-runbook.md) — routine checks, incidents,
  and release gates.
