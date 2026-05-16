# MVP Release Checklist

Use this checklist before promoting staging to production.

## Security gates

- [ ] `ATLAS_API_DOCS_ENABLED=false` in production.
- [ ] `ATLAS_CORS_ALLOWED_ORIGINS` contains only production frontend domains.
- [ ] `ATLAS_TRUSTED_HOSTS` contains only production hostnames.
- [ ] `ATLAS_ENFORCE_HTTPS_REDIRECT=true`.
- [ ] No `ATLAS_SUPABASE_SERVICE_KEY` or `ATLAS_BROWSER_USE_API_KEY` exposure in client responses.
- [ ] CI secret scan is green.

## Functional gates

- [ ] User can sign in via `/auth/login`.
- [ ] User sign-up flow handles both immediate session and email-confirmation-required states.
- [ ] `/me/quota` returns `used/limit/remaining`.
- [ ] First 5 Ask requests succeed, 6th returns `status=quota_exceeded`.
- [ ] Search/source endpoints return expected payloads.
- [ ] Web app `/app` renders and supports mobile layout.
- [ ] Ask endpoints return timeout payload (`status=timeout`) when exceeding `ATLAS_ASK_REQUEST_TIMEOUT_SECONDS`.

## Operational gates

- [ ] `pytest -q` passes in CI.
- [ ] `/health` returns 200 on deployed service.
- [ ] `/ready` returns 200 on deployed service.
- [ ] Logs include auth failures, quota exceeded, and rate-limit events.
- [ ] Alerting configured for API 5xx spikes and auth/ask anomaly spikes.
- [ ] Deployment is single-instance (rate limiting is in-memory for MVP).

## Rollback

1. Re-deploy the previous successful Render image/service revision.
2. Verify `/health`, `/search/sources`, and `/app` recover.
3. If rollback was caused by data migration issues, restore DB snapshot as needed and re-run smoke.
