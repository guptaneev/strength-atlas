# Docs

This repository keeps only durable product, architecture, engineering, and operational documentation. Historical checkpoints and superseded plans are intentionally removed.

- [Strength Atlas PRD + Engineering Design (V1)](product/strength-atlas-prd-v1.md) - canonical product requirements and system-design context for V1.
- [Browser Use Cloud SDK Reference](engineering/browser-use-cloud-sdk-reference.md) - local Browser Use API and SDK reference snapshot for engineering work.
- [Strength Atlas Full-Stack MVP Technical Plan](engineering/strength-atlas-cli-mvp-technical-plan.md) - active implementation roadmap for CLI + API + web MVP, including architecture decisions, contracts, crawl rules, and tests.
- [Search Eval Fixture](engineering/search-eval-fixture.json) - baseline relevance checks for CLI search quality regression tracking.
- [Domain Crawl Policies Example](engineering/domain-crawl-policies.example.json) - sample domain-specific seed and per-domain limit policy file for ops scale-up.
- [Ask Atlas API Contracts (V0)](engineering/ask-atlas-api-contracts-v0.md) - request, response, and evidence contracts.
- [Learned Reranker](engineering/reranker.md) - current model, datasets, evaluation, reproduction, and serving contract.
- [Strength Atlas Current-State Summary](architecture/strength-atlas-current-state.md) - readable overview of the current pipeline, technologies, data model, interfaces, and future boundaries.
- [Operations Runbook](operations/ops-runbook.md) - operations, release gates, incidents, security, and rollback.
- [Production Deployment](operations/production-deployment.md) - canonical Cloud Run + Supabase deployment, cost controls, model activation, smoke tests, and rollback.
