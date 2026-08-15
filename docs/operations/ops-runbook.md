# Operations Runbook (MVP)

For release configuration, model artifacts, deployment, smoke tests, and
rollback, use the [production deployment guide](production-deployment.md).

## Daily ingest reliability workflow

1. Review backlog and stale succeeded sources:
   - `atlas ops backlog --json`
2. Review admission quality and blocked domains:
   - `atlas ops domain-quality --domain-policy-file docs/engineering/domain-crawl-policies.example.json --json`
3. Run dry-run before production ops changes:
   - `atlas ops dry-run --json`
4. Execute controlled batch:
   - `atlas ops run --json`
5. Review run metrics:
   - `atlas ops metrics --limit 20 --json`

## Ask API reliability checks

1. Watch for spikes in:
   - 5xx responses
   - `auth_error`
   - `quota_exceeded`
   - `rate_limited`
2. Validate quota behavior using a test user:
   - sign in via `/auth/login`
   - confirm `GET /me/quota`
   - submit Ask until blocked at configured limit
3. Validate readiness before and after deploy:
   - `GET /health` should return `200` with `{"status":"ok"}`
   - `GET /ready` should return `200` only when DB and JWKS checks are healthy

## Incident patterns and actions

### High 5xx rate

1. Check deployment revision and recent config changes.
2. Verify DB and Supabase auth connectivity.
3. Route traffic to the previous stable Cloud Run revision if unresolved within 15 minutes.

### Auth failure spike

1. Verify Supabase JWT issuer/JWKS settings:
   - `ATLAS_SUPABASE_URL`, `ATLAS_SUPABASE_JWT_ISSUER`, `ATLAS_SUPABASE_JWKS_URL`
2. Confirm clock sync on host.
3. Check if Supabase rotated signing keys and restart service if needed.

### Quota unexpectedly denying early

1. Inspect `ask_quota_usage` rows for affected users.
2. Confirm `ATLAS_ASK_LIFETIME_LIMIT` value.
3. If needed, manually reset `used_count` for support-approved users.

### Ask abuse / burst traffic

1. Tighten:
   - `ATLAS_ASK_IP_RATE_LIMIT_MAX_REQUESTS`
   - `ATLAS_ASK_USER_RATE_LIMIT_MAX_REQUESTS`
2. Add temporary reverse-proxy/WAF throttling.
3. Keep deployment single-instance for MVP rate-limit consistency.

## Security hygiene

1. Never expose:
   - `ATLAS_SUPABASE_SERVICE_KEY`
   - `ATLAS_BROWSER_USE_API_KEY`
2. Rotate keys immediately if leaked.
3. Keep `.env` local-only and excluded from git.

## Release checklist

- [ ] Full test suite and CI pass.
- [ ] Database migrations are at head and apply cleanly.
- [ ] Secret scan is green; tracked files contain no real credentials.
- [ ] Production API docs are disabled and HTTPS redirect is enabled.
- [ ] CORS origins and trusted hosts contain only production values.
- [ ] `/health` and `/ready` return 200 after deployment.
- [ ] Authentication, Ask quota, source search, program search, and reranking smoke tests pass.
- [ ] Logging covers 5xx, authentication, quota, and rate-limit failures.
- [ ] README and durable docs match the deployed command surface.

Rollback by deploying the previous successful image, checking `/health`,
`/search/sources`, and `/app`, then restoring the database snapshot only if a
migration or data change requires it.
