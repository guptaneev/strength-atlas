# Corpus expansion v1 — checkpoint 1

**Captured:** 2026-08-15  
**Status:** first controlled expansion wave active; no second-wave discovery opened

## Outcome

The live corpus increased from **83 to 133 sources**, **56 to 76 documents**,
and **210 to 306 structured program records**. That is a net increase of 50
discovered sources, 20 extracted documents, and 96 programs during this wave.

Discovery was capped at 20 candidates per new domain. Extraction used the
per-domain limits in
`docs/engineering/domain-crawl-policies.corpus-expansion-v1.json`, one active
crawl per domain, a 180-second timeout, and the normal retry policy.

## Coverage added

| Domain / track | Sources | Extracted | Pending | Structured programs | Coverage contribution |
|---|---:|---:|---:|---:|---|
| California Strength | 7 | 4 | 3 | 31 | Olympic lifting, squat specialization, general fitness, conditioning |
| PowerliftingToWin | 20 | 5 | 15 | 39 | Powerlifting programming, novice plans, periodization, training variables |
| RP Strength | 10 | 4 | 6 | 14 | Hypertrophy, volume landmarks, muscle-specific programming |
| Starting Strength | 13 | 2 | 11 | 6 | Novice linear progression, barbell programming, intermediate transition |
| Barbell Medicine (expanded existing queue) | 68 | 35 | 33 | 176 | Hypertrophy and rehabilitation template coverage |
| Stronger By Science (existing) | 15 | 15 | 0 | 40 | General strength, one-lift programs, autoregulation |

Two capped crawl jobs remained active when this checkpoint was captured. They
belong to existing bounded queues; no new discovery or unbounded run was
started after this checkpoint.

## Quality and operations

- All new-domain sources extracted so far have terminal `succeeded` source
  status; no new domain has been paused.
- The campaign ledger recorded nine successful completed items and no terminal
  run failure at the time of its latest summary. Its recorded completed work
  cost was about $0.84; the source/document counts above are the authoritative
  live-database totals because some in-flight jobs finish after a CLI run exits.
- Two Barbell Medicine product-page extraction attempts failed after retry.
  The source records remain pending for controlled follow-up; this did not trip
  the domain's 40% recent-failure admission threshold.

## Retrieval implications

This expansion directly increases coverage in categories that were absent or
weak in the baseline analysis: novice programming, hypertrophy volume,
Olympic/conditioning programs, rehabilitation templates, and dedicated
powerlifting-programming material. It does not by itself solve all candidate
recall gaps. The next retrieval checkpoint should rerun the representative
query suite and add query intent expansion/semantic retrieval for terminology
that full-text search still misses.

## Safe next wave

After the two active jobs settle, inspect per-domain parse confidence, program
yield, failure codes, and duplicate-source rate. Then extract up to six more
pending sources per healthy new domain, while holding Barbell Medicine at its
current cap until its product-page failures are categorized.
