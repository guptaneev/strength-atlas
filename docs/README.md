# Docs

This repository stores durable project context in versioned documentation. Product intent lives under `docs/product`, active implementation guidance under `docs/engineering`, current-state architecture summaries under `docs/architecture`, future initiatives under `docs/roadmap`, and operational guidance under `docs/operations`.

- [Strength Atlas PRD + Engineering Design (V1)](product/strength-atlas-prd-v1.md) - canonical product requirements and system-design context for V1.
- [Browser Use Cloud SDK Reference](engineering/browser-use-cloud-sdk-reference.md) - local Browser Use API and SDK reference snapshot for engineering work.
- [Strength Atlas Full-Stack MVP Technical Plan](engineering/strength-atlas-cli-mvp-technical-plan.md) - active implementation roadmap for CLI + API + web MVP, including architecture decisions, contracts, crawl rules, and tests.
- [Search Eval Fixture](engineering/search-eval-fixture.json) - baseline relevance checks for CLI search quality regression tracking.
- [Domain Crawl Policies Example](engineering/domain-crawl-policies.example.json) - sample domain-specific seed and per-domain limit policy file for ops scale-up.
- [Ask Atlas API Contracts (V0)](engineering/ask-atlas-api-contracts-v0.md) - API-first request/response and evidence contracts for future Ask Atlas services.
- [Semantic Layer V0](engineering/semantic-layer-v0.md) - non-disruptive embedding hook plan that preserves current CLI search behavior.
- [Strength Atlas ML Development Plan](roadmap/strength-atlas-ml-development-plan.md) - future applied-ML roadmap for learning-to-rank, evaluation, fine-tuning, inference optimization, and production integration.
- [Strength Atlas ML Learning Plan](roadmap/strength-atlas-ml-learning-plan.md) - learner-first companion with incremental milestones, AI-assisted study practices, and evidence-based exit checks.
- [Strength Atlas Current-State Summary](architecture/strength-atlas-current-state.md) - readable overview of the current pipeline, technologies, data model, interfaces, and future boundaries.
- [MVP Release Checklist](operations/mvp-release-checklist.md) - production cutover, security gates, and rollback checklist.
- [Operations Runbook](operations/ops-runbook.md) - day-to-day ops workflow, incident responses, and security hygiene.
