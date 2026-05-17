# Master Publish Checklist

Use this checklist before merging release-critical changes into `master`.

## Code and Tests

- [ ] `pytest` passes locally
- [ ] CI test workflow is green
- [ ] Alembic migrations are at head and apply cleanly

## Security

- [ ] Secret scan workflow is green
- [ ] No real keys in tracked files (`.env`, logs, docs, fixtures)
- [ ] `.env.example` is present and uses placeholders only
- [ ] `.gitignore` excludes local env/secrets and runtime artifacts
- [ ] Documentation contains no local absolute filesystem links

## Operational Smoke Test

- [ ] Add/verify allowlisted domain
- [ ] Run discovery with known seed URL
- [ ] Extract at least one source URL
- [ ] Confirm source show output includes document and crawl metadata
- [ ] Confirm source + program search return expected rows

## Release Notes and Docs

- [ ] README command surface matches current CLI
- [ ] `docs/README.md` links resolve correctly
- [ ] Technical plan and PRD status fields are current
