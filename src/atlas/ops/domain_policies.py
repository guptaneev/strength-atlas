from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DomainPolicy:
    seed_urls: list[str]
    per_domain_limit: int | None = None
    stale_after_days: int | None = None
    admission_min_succeeded_sources: int | None = None
    admission_max_recent_failure_rate: float | None = None
    admission_min_avg_parse_confidence: float | None = None
    admission_max_zero_program_rate: float | None = None
    admission_recent_crawl_window: int | None = None


def load_domain_policies(path: str | None) -> dict[str, DomainPolicy]:
    if not path:
        return {}
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"domain policy file not found: {path}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("domain policy file must be a JSON object")

    policies: dict[str, DomainPolicy] = {}
    for domain, config in payload.items():
        if not isinstance(domain, str) or not isinstance(config, dict):
            continue
        seed_urls = [str(url) for url in config.get("seed_urls", []) if isinstance(url, str)]
        per_domain_limit = config.get("per_domain_limit")
        stale_after_days = config.get("stale_after_days")
        admission_min_succeeded_sources = config.get("admission_min_succeeded_sources")
        admission_max_recent_failure_rate = config.get("admission_max_recent_failure_rate")
        admission_min_avg_parse_confidence = config.get("admission_min_avg_parse_confidence")
        admission_max_zero_program_rate = config.get("admission_max_zero_program_rate")
        admission_recent_crawl_window = config.get("admission_recent_crawl_window")
        policies[domain.strip().lower()] = DomainPolicy(
            seed_urls=seed_urls,
            per_domain_limit=int(per_domain_limit) if per_domain_limit is not None else None,
            stale_after_days=int(stale_after_days) if stale_after_days is not None else None,
            admission_min_succeeded_sources=(
                int(admission_min_succeeded_sources)
                if admission_min_succeeded_sources is not None
                else None
            ),
            admission_max_recent_failure_rate=(
                float(admission_max_recent_failure_rate)
                if admission_max_recent_failure_rate is not None
                else None
            ),
            admission_min_avg_parse_confidence=(
                float(admission_min_avg_parse_confidence)
                if admission_min_avg_parse_confidence is not None
                else None
            ),
            admission_max_zero_program_rate=(
                float(admission_max_zero_program_rate)
                if admission_max_zero_program_rate is not None
                else None
            ),
            admission_recent_crawl_window=(
                int(admission_recent_crawl_window)
                if admission_recent_crawl_window is not None
                else None
            ),
        )
    return policies
