# Docs

This repository stores durable project context in versioned documentation. Product intent, scope, and system design live under `docs/product`, while technical integration references live under `docs/engineering`.

- [Strength Atlas PRD + Engineering Design (V1)](product/strength-atlas-prd-v1.md) - canonical product requirements and system-design context for V1.
- [Browser Use Cloud SDK Reference](engineering/browser-use-cloud-sdk-reference.md) - local Browser Use API and SDK reference snapshot for engineering work.
- [Strength Atlas CLI MVP Technical Plan](engineering/strength-atlas-cli-mvp-technical-plan.md) - active technical roadmap for the Python CLI MVP, including stack decisions, commands, schema contracts, crawl rules, and tests.
- [Search Eval Fixture](engineering/search-eval-fixture.json) - baseline relevance checks for CLI search quality regression tracking.
- [Domain Crawl Policies Example](engineering/domain-crawl-policies.example.json) - sample domain-specific seed and per-domain limit policy file for ops scale-up.
- [Ask Atlas API Contracts (V0)](engineering/ask-atlas-api-contracts-v0.md) - API-first request/response and evidence contracts for future Ask Atlas services.
- [Semantic Layer V0](engineering/semantic-layer-v0.md) - non-disruptive embedding hook plan that preserves current CLI search behavior.
- [MVP Release Checklist](operations/mvp-release-checklist.md) - production cutover, security gates, and rollback checklist.
- [Operations Runbook](operations/ops-runbook.md) - day-to-day ops workflow, incident responses, and security hygiene.
