# Security Policy

## Supported Scope

This repository currently supports a CLI-only MVP on the `master` branch.

Security-sensitive surfaces:

- Supabase credentials (`ATLAS_SUPABASE_SERVICE_KEY`, `ATLAS_DATABASE_URL`)
- Browser Use API key (`ATLAS_BROWSER_USE_API_KEY`)
- Extracted artifacts and crawl metadata stored in Supabase

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

## Pre-Merge Security Gates

- CI tests pass
- Secret scan passes
- Docs contain no local absolute paths
- `.env.example` updated when config contract changes
- Migration changes reviewed for data integrity and privilege impact
