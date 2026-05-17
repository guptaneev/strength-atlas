---
purpose: Canonical product and system-design context for Strength Atlas V1
version: V1
status: active
owner: Strength Atlas Maintainers
---

# Strength Atlas PRD + Engineering Design (V1)

## 1. Overview

### Product summary

Strength Atlas is a training intelligence platform for powerlifters and serious lifters. It turns fragmented web content - training programs, coach articles, athlete interviews, forum discussions, and related pages - into structured, searchable training knowledge.

### Why this exists

Strength knowledge is scattered across many inconsistent websites. Browser Use Cloud is a strong fit because it provides managed browser automation, browser sessions, profiles, skills, and related cloud infrastructure for navigating those messy sources.

### Core user value

A user can ask:

- "What do 405+ bench lifters commonly do?"
- "Find me 4-day bench-focused intermediate programs."
- "What accessory work shows up most often in strong deadlift programs?"

And get:

- a summarized answer,
- structured evidence,
- source-backed snippets,
- confidence indicators.

## 2. PRD

### Target users

Primary:

- intermediate to advanced powerlifters
- serious gym lifters
- online strength coaches
- powerlifting content creators

Secondary:

- strength gyms
- training app builders
- sports performance researchers

### Problem statement

Today, lifters find training knowledge through:

- Reddit threads,
- old forum posts,
- coach blogs,
- PDFs,
- interviews,
- scattered program pages.

The problem is not lack of information. It is fragmentation and lack of structure.

### Product goals

For V1, Strength Atlas should:

1. index useful public strength-training sources,
2. normalize them into searchable program and training entities,
3. answer source-grounded user questions,
4. show provenance for every major answer.

### Non-goals

V1 will not:

- automate posting or interacting on third-party sites,
- mass-create accounts,
- provide medical or injury advice,
- replace a human coach,
- ingest the whole internet.

### Core features

#### 2.1 Program Discovery

Users can search for programs by:

- lift focus,
- specialization,
- days per week,
- experience level,
- equipment,
- tags.

Example:

`4 day intermediate bench specialization`

Returns:

- ranked programs,
- coach or author,
- split,
- progression style,
- source link,
- extracted summary.

#### 2.2 Ask Atlas

Natural language Q&A over indexed training content.

Example:

`What bench frequency appears most often in strong bench programs?`

Returns:

- short answer,
- key patterns,
- supporting sources,
- confidence statement.

#### 2.3 Evidence Cards

Every answer should show:

- source title,
- source type,
- extracted snippet,
- crawl date,
- confidence score.

#### 2.4 Source Explorer

A user can inspect a source page and see:

- extracted metadata,
- linked programs,
- tagged entities,
- raw snippets used for answers.

### Success metrics

Product:

- percent of questions answered with source-backed evidence
- search success rate
- repeat weekly users
- saved searches per active user

Data quality:

- extraction success rate
- structured parse confidence
- citation coverage
- duplicate-source reduction rate

Ops:

- cost per indexed source
- cost per answered query
- browser task failure rate
- domain block and error rate

## 3. User stories

### Lifter

"I want to find programs similar to what strong bench specialists actually use."

### Coach

"I want to compare common volume and frequency patterns across high-performing programs."

### Content creator

"I want evidence-backed summaries of training patterns without manually reading 50 pages."

## 4. Functional requirements

### Search

- keyword search
- filtered search
- semantic retrieval
- structured ranking

### Q&A

- natural language input
- retrieval grounded in indexed content
- answer only from available evidence
- uncertainty when evidence is weak

### Program records

Each program should try to store:

- name
- coach or author
- source URL
- days per week
- split
- focus
- progression type
- intensity cues
- exercise list
- confidence

### Source records

Each source should try to store:

- URL
- domain
- source type
- title
- author if known
- extracted date
- last crawled date
- raw text or snapshot references

## 5. Technical architecture

### 5.1 High-level architecture

```text
User
  ->
Next.js Frontend
  ->
App API
  ->
Retrieval / Answer Service
  |\
  | \-> Redis
  \----> Postgres + pgvector
  ^
Normalization / Extraction Pipeline
  ^
Browser Orchestrator
  ^
Browser Use Cloud
  ^
Target websites
```

### 5.2 Frontend

Recommended stack:

- Next.js
- TypeScript
- Tailwind
- shadcn/ui
- TanStack Query
- PostHog

Why:

- fast development
- good SSR and SEO for public program pages
- strong app-router ergonomics
- easy auth and API integration

Main frontend surfaces:

- homepage and search
- Ask Atlas
- program detail page
- source detail page
- user dashboard
- admin console

### 5.3 Backend

Recommended split:

App and API layer:

- FastAPI or Next.js route handlers

Data and ingestion layer:

- Python workers
- orchestration service
- normalization pipeline

Why Python for ingestion:

The browser automation and extraction layer will likely benefit from Python-first orchestration and data parsing.

Core backend services:

1. App API
2. Retrieval and answer service
3. Crawl orchestrator
4. Browser task runner
5. Parser and normalizer
6. Admin and ops service

### 5.4 Storage

Postgres:

Use for:

- users
- workspaces
- programs
- sources
- claims
- entities
- tasks
- profiles and sessions metadata

pgvector:

Use for:

- semantic retrieval on extracted chunks

Redis:

Use for:

- rate limiting
- caching
- queue state
- job locks

Object storage:

Use S3-compatible storage for:

- raw HTML snapshots
- screenshots
- extracted JSON
- PDFs and downloaded artifacts

## 6. Browser Use integration design

Browser Use Cloud supports:

- AI agent tasks,
- browser sessions,
- persistent profiles,
- skills,
- authentication helpers including profile sync and domain-scoped secrets.

### 6.1 When to use which Browser Use primitive

#### Agent Tasks

Use for broad, inconsistent browsing flows.

Examples:

- find candidate training pages on a coach site
- search a site for relevant program pages
- inspect a messy article layout

Browser Use prices AI agent tasks with a task-init fee plus per-step model pricing.

#### Sessions

Use for multi-step workflows that need continuity. A session can be created explicitly and reused across multiple steps, and Browser Use documents sessions as the right primitive for stateful, multi-step browser workflows.

Examples:

- open a source page
- follow internal links
- inspect related pages
- save artifacts and stop

#### Profiles

Use when persistent browser state matters. Browser Use documents profiles as persistent browser state that can store login state and cookies and be reused across sessions.

Examples:

- approved internal editorial login state
- stable source-specific browsing state
- future user-owned integrations

#### Skills

Use when a repeated site flow becomes stable. Browser Use describes skills as reusable, deterministic APIs for repeated website interactions.

Examples:

- extract metadata from a known program template
- pull supplement label fields from a repeated storefront layout

### 6.2 Internal Browser Use entity model

#### `browser_profiles`

- `id`
- `browser_use_profile_id`
- `owner_type`
- `owner_id`
- `purpose`
- `status`
- `created_at`

#### `browser_sessions`

- `id`
- `browser_use_session_id`
- `profile_id`
- `domain`
- `task_type`
- `proxy_region`
- `status`
- `live_url`
- `started_at`
- `stopped_at`

#### `browser_tasks`

- `id`
- `session_id`
- `task_type`
- `prompt`
- `status`
- `step_count`
- `estimated_cost_usd`
- `started_at`
- `completed_at`

#### `browser_skills`

- `id`
- `browser_use_skill_id`
- `site_name`
- `schema_version`
- `status`

## 7. Source ingestion design

### 7.1 Discovery pipeline

Purpose: find useful candidate URLs.

Flow:

1. start from allowlisted domains or seed URLs
2. run Browser Use task to explore relevant sections
3. collect candidate URLs
4. canonicalize URLs
5. dedupe
6. enqueue extraction

### 7.2 Extraction pipeline

Purpose: turn a candidate URL into structured content.

Flow:

1. create or reuse session
2. navigate directly to URL
3. extract:
   - title
   - source type
   - main text
   - program metadata
   - structured claims and snippets
4. save raw artifacts
5. normalize entities
6. store embeddings
7. mark extraction status

### 7.3 Refresh pipeline

Purpose: recrawl important sources without wasting spend.

Policy:

- high-value dynamic domains: 14 days
- stable program pages: 60 to 90 days
- unchanged pages: back off progressively

## 8. Normalization and retrieval

### 8.1 Normalized entities

Examples:

- lifter
- coach
- program
- exercise
- lift
- progression type
- split
- frequency
- volume claim

### 8.2 Claim extraction

Claims might look like:

- `bench 3x/week`
- `top sets at RPE 8`
- `12 weekly working sets`
- `close grip bench as primary accessory`

Every claim should store:

- source document
- raw text
- normalized interpretation
- confidence score

### 8.3 Answer generation

Answer generation should:

1. retrieve structured entities and chunks,
2. synthesize only from retrieved evidence,
3. show supporting evidence cards,
4. return `insufficient evidence` when necessary.

## 9. Rate limiting and traffic policy

There are two separate problems:

1. user rate limits on your product,
2. job and concurrency limits for Browser Use and target websites.

### 9.1 User-facing rate limits

Anonymous:

- search: 10 per hour
- Ask Atlas: 3 per day

Free authenticated:

- search: 60 per hour
- Ask Atlas: 20 per day
- one active async query

Pro:

- search: 300 per hour
- Ask Atlas: 100 per day
- five active async queries

Team and coach:

- workspace cap: 1000 per hour
- ten concurrent async jobs

Enforcement:

Use Redis token buckets keyed by:

- `user_id`
- `workspace_id`
- `endpoint`

Also add:

- hard caps on expensive endpoints
- abuse scoring
- cooldowns after repeated failures

### 9.2 Browser Use and internal job limits

Browser Use's pricing page currently lists browser sessions, skills, proxy data, and task pricing, and its FAQ notes 429 handling and concurrency constraints by plan. It also states session timeouts can run up to 4 hours.

Recommended internal V1 limits:

- global active sessions: 5 to 10
- per-domain active sessions: 1
- max tasks per domain per minute: 3
- max retries per job: 2
- backoff: 2s -> 5s -> 10s
- auto-cooldown after repeated domain failures: 24h

Why:

This keeps:

- cost under control,
- browsing respectful,
- noisy failures contained.

### 9.3 Site-respect rules

Even though Browser Use Cloud advertises stealth browsers, CAPTCHA solving, residential proxies, and managed infra, the product should still operate conservatively and permission-respectfully.

Internal rules:

- allowlist domains for V1
- no high-burst crawling
- direct-URL extraction preferred
- no repeated login retries
- no mass account creation
- no "retry until it works" logic
- use cooldowns on block signals

## 10. Profiles, auth, and secrets

Browser Use's authentication docs describe:

- syncing local browser cookies into a cloud profile,
- domain-scoped secrets,
- 1Password integration with TOTP and 2FA support.

### 10.1 Profile policy

Use three categories:

System profiles:

- owned by the company for approved sources

Site profiles:

- one profile per service or domain family where persistent state is needed

User profiles:

- not needed in V1, but useful later for user-owned integrations

Rule:

Never use one giant shared profile across unrelated sites.

### 10.2 Secrets policy

- store in cloud secret manager
- inject only at runtime
- require explicit allowed-domain mapping
- never include secrets in prompts
- audit every secrets-backed task

### 10.3 1Password policy

If used:

- dedicated service account
- dedicated vault per environment
- read-only minimal access
- only for approved internal operations

## 11. Data model

### `sources`

- `id`
- `url`
- `canonical_url`
- `domain`
- `source_type`
- `allowlisted`
- `crawl_policy_id`
- `last_crawled_at`
- `status`

### `documents`

- `id`
- `source_id`
- `title`
- `author`
- `raw_text`
- `html_snapshot_path`
- `extracted_json_path`
- `published_at`
- `crawl_id`

### `programs`

- `id`
- `name`
- `coach_name`
- `source_document_id`
- `days_per_week`
- `specialization`
- `experience_level`
- `progression_type`
- `split_type`
- `confidence`

### `claims`

- `id`
- `document_id`
- `entity_type`
- `claim_type`
- `raw_text`
- `normalized_value`
- `confidence`

### `entities`

- `id`
- `entity_type`
- `canonical_name`
- `aliases_json`

### `jobs`

- `id`
- `job_type`
- `target_url`
- `domain`
- `status`
- `retry_count`
- `started_at`
- `completed_at`

## 12. Cost controls

Browser Use's official pricing includes:

- AI task init fee,
- per-step pricing,
- browser session hourly pricing,
- skill creation and execution pricing,
- proxy data charges,
- session timeout limit up to 4 hours.

Cost controls for V1:

- direct URL navigation whenever possible
- hard cap on max task steps
- short session TTLs
- dedupe before crawl
- use lower-cost flows for discovery
- convert repeated workflows into skills
- store raw artifacts so re-parsing does not require re-crawling

Internal budget guardrails:

- max daily browser spend
- max spend per domain and day
- max spend per user query class
- auto-disable unhealthy domains

## 13. Reliability and observability

Track:

- extraction success percent
- average task steps
- average cost per source
- average answer latency
- domain-specific failure rate
- citation coverage percent
- duplicate-source rate

Alert on:

- 429 spike
- domain failure spike
- session leak
- abnormal spend
- answer generation without evidence

### Debugging

Browser Use sessions support live inspection and live URL flows in the sessions docs, which is useful for debugging failed jobs.

## 14. Security

### Requirements

- encrypted secrets at rest
- signed artifact URLs
- row-level auth for workspaces
- audit logs for credentialed actions
- production and staging separation
- limited profile access by service role

### Retention

Suggested:

- raw HTML and screenshots: 30 to 90 days
- normalized data: retained
- task and session metadata: 180 days

Browser Use's pricing and business materials mention enterprise and privacy-oriented options such as zero data retention and other compliance-related offerings depending on plan.

## 15. Recommended stack

### Frontend

- Next.js
- TypeScript
- Tailwind
- shadcn/ui
- TanStack Query

### Backend

- FastAPI
- Python worker services

### Infra

- Postgres + pgvector
- Redis
- S3-compatible storage
- Temporal or Celery
- Sentry
- PostHog

### Browser layer

- Browser Use Cloud

## 16. MVP scope

### Phase 1

- 20 to 50 approved domains
- discovery and extraction
- program search
- source explorer
- manual QA loop

### Phase 2

- Ask Atlas
- evidence cards
- semantic retrieval
- program comparison

### Phase 3

- coach and team workspaces
- saved searches
- exports
- more skills on stable domains
