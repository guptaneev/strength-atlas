from types import SimpleNamespace

from atlas.ops.admission import DomainQualitySnapshot, build_domain_quality_report
from atlas.ops.domain_policies import DomainPolicy


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _Session:
    def __init__(self, domains):
        self._domains = domains

    def execute(self, _query):
        return _Result(self._domains)


def test_build_domain_quality_report_blocks_domain_when_policy_threshold_fails(monkeypatch) -> None:
    domains = [
        SimpleNamespace(id=1, domain="example.com", allowlisted=True, paused=False),
    ]
    session = _Session(domains)
    monkeypatch.setattr(
        "atlas.ops.admission.build_domain_quality_snapshot",
        lambda *_args, **_kwargs: DomainQualitySnapshot(
            domain="example.com",
            succeeded_sources=10,
            recent_crawl_window=20,
            recent_attempted_crawls=20,
            recent_failed_crawls=8,
            recent_failure_rate=0.4,
            avg_parse_confidence=0.9,
            succeeded_with_documents=10,
            zero_program_succeeded_sources=1,
            zero_program_rate=0.1,
        ),
    )

    report = build_domain_quality_report(
        session,
        domain_policies={
            "example.com": DomainPolicy(seed_urls=[], admission_max_recent_failure_rate=0.2),
        },
    )

    assert report["totals"]["domains_count"] == 1
    assert report["totals"]["blocked"] == 1
    assert report["by_domain"][0]["admitted"] is False
    assert report["by_domain"][0]["admission_block_reason"] == "domain_quality_recent_failure_rate_exceeded"


def test_build_domain_quality_report_admits_when_no_admission_thresholds(monkeypatch) -> None:
    domains = [
        SimpleNamespace(id=1, domain="example.com", allowlisted=True, paused=False),
    ]
    session = _Session(domains)
    monkeypatch.setattr(
        "atlas.ops.admission.build_domain_quality_snapshot",
        lambda *_args, **_kwargs: DomainQualitySnapshot(
            domain="example.com",
            succeeded_sources=1,
            recent_crawl_window=20,
            recent_attempted_crawls=0,
            recent_failed_crawls=0,
            recent_failure_rate=None,
            avg_parse_confidence=None,
            succeeded_with_documents=0,
            zero_program_succeeded_sources=0,
            zero_program_rate=None,
        ),
    )

    report = build_domain_quality_report(
        session,
        domain_policies={"example.com": DomainPolicy(seed_urls=[])},
    )

    assert report["totals"]["domains_count"] == 1
    assert report["totals"]["admitted"] == 1
    assert report["totals"]["blocked"] == 0
    assert report["by_domain"][0]["admitted"] is True
