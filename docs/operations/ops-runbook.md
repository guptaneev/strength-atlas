# Operations runbook

Use this runbook for routine corpus work and incident response. For deployment
details, use the [production deployment guide](production-deployment.md).

## Routine operator workflow

```bash
atlas ops backlog --json
atlas ops domain-quality --domain-policy-file docs/engineering/domain-crawl-policies.example.json --json
atlas ops dry-run --json
atlas ops run --json
atlas ops metrics --limit 20 --json
```

Review the dry-run before a production batch. Investigate blocked domains,
failed crawls, and stale successful sources before increasing scope.

## Service checks

- `/health` returns `200` when the process is live.
- `/ready` returns `200` only when database and authentication readiness pass.
- `/retrieval/status` reports the configured model and its load state.
- Watch 5xx, 504, auth failures, quota events, rate-limit events, and
  `reranker_fallback` logs.

## Incident response

### High 5xx or readiness failures

1. Inspect the active Cloud Run revision and recent logs.
2. Check database connectivity, Supabase availability, and secret bindings.
3. Route traffic to the previous verified revision if the issue is not resolved
   promptly.

### Reranker fallback or slow first request

1. Confirm `/retrieval/status` after a ranked search.
2. Check model archive URL, archive checksum, weights checksum, and runtime
   service-account access.
3. Review timeout and memory pressure before changing the configured reranker
   timeout. Baseline order is the expected safe fallback.

### Auth, quota, or rate-limit anomaly

1. Verify Supabase URL, JWKS/issuer configuration, and system time.
2. Check the lifetime quota and current `ATLAS_ASK_*` configuration.
3. Tighten rate limits or introduce upstream throttling for an abuse event.
4. Reset a quota only through an approved support process.

## Release gate

- [ ] Clean worktree and completed CI-quality checks
- [ ] Migration job succeeds
- [ ] Production health and readiness checks pass
- [ ] Program search, source search, sign-in, and one Ask response are checked
- [ ] Reranker status and evidence cards are verified
- [ ] CORS, trusted hosts, HTTPS redirect, secrets, and rate limits are correct
- [ ] Recent logs contain no unexplained errors or recurring fallback events
