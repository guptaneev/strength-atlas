# Security Policy

## Supported Scope

This repository supports an operator CLI and a public Cloud Run web/API
service. The supported production stack is Cloud Run, Supabase, and private
Google Cloud Storage model artifacts.

Security-sensitive surfaces:

- Supabase credentials (`ATLAS_SUPABASE_SERVICE_KEY`, `ATLAS_DATABASE_URL`)
- Browser Use API key (`ATLAS_BROWSER_USE_API_KEY`)
- Extracted artifacts and crawl metadata stored in Supabase
- Model archive access granted to the Cloud Run runtime identity

## Reporting a Vulnerability

If you discover a vulnerability:

1. **Do not** open a public issue with exploit details.
2. Email the maintainer with:
   - vulnerability summary
   - impact and affected components
   - reproduction steps
   - optional remediation suggestion
3. Include "Strength Atlas Security" in the subject line.

Until a dedicated security mailbox exists, use the maintainer contact listed in the repository profile.

## Secure Development Requirements

- Never commit real credentials, tokens, cookies, or session IDs.
- Keep `.env` local-only. Use `.env.example` placeholders for shared config shape.
- Rotate keys immediately on suspected exposure.
- Treat crawl artifacts as potentially sensitive and limit access to operator roles.
- Prefer least-privilege credentials for all non-local environments.
- Keep the model bucket private and grant object-read access only to the runtime
  identity.

## Pre-Merge Security Gates

- CI tests pass
- Secret scan passes
- Docs contain no local absolute paths
- `.env.example` updated when config contract changes
- Migration changes reviewed for data integrity and privilege impact
- Cloud Run deployment settings preserve explicit hosts, HTTPS redirect, and
  bounded instance/concurrency limits
