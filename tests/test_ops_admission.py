from types import SimpleNamespace

from atlas.ops.admission import DomainQualitySnapshot, assess_domain_admission
from atlas.ops.domain_policies import DomainPolicy


def _snapshot(**kwargs) -> DomainQualitySnapshot:
    base = DomainQualitySnapshot(
        domain="example.com",
        succeeded_sources=10,
        recent_crawl_window=20,
        recent_attempted_crawls=20,
        recent_failed_crawls=2,
        recent_failure_rate=0.1,
        avg_parse_confidence=0.9,
        succeeded_with_documents=10,
        zero_program_succeeded_sources=1,
        zero_program_rate=0.1,
    )
    return base.__class__(**{**base.__dict__, **kwargs})


def test_assess_domain_admission_blocks_when_recent_failure_rate_exceeds_threshold(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.ops.admission.build_domain_quality_snapshot",
        lambda *_args, **_kwargs: _snapshot(recent_failure_rate=0.45),
    )
    decision = assess_domain_admission(
        SimpleNamespace(),
        domain_row=SimpleNamespace(id=1, domain="example.com"),
        policy=DomainPolicy(seed_urls=[], admission_max_recent_failure_rate=0.2),
    )
    assert decision.admitted is False
    assert decision.reason == "domain_quality_recent_failure_rate_exceeded"


def test_assess_domain_admission_blocks_when_missing_recent_history(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.ops.admission.build_domain_quality_snapshot",
        lambda *_args, **_kwargs: _snapshot(recent_attempted_crawls=0, recent_failure_rate=None),
    )
    decision = assess_domain_admission(
        SimpleNamespace(),
        domain_row=SimpleNamespace(id=1, domain="example.com"),
        policy=DomainPolicy(seed_urls=[], admission_max_recent_failure_rate=0.2),
    )
    assert decision.admitted is False
    assert decision.reason == "domain_quality_insufficient_recent_crawl_history"


def test_assess_domain_admission_passes_when_thresholds_are_met(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.ops.admission.build_domain_quality_snapshot",
        lambda *_args, **_kwargs: _snapshot(),
    )
    decision = assess_domain_admission(
        SimpleNamespace(),
        domain_row=SimpleNamespace(id=1, domain="example.com"),
        policy=DomainPolicy(
            seed_urls=[],
            admission_min_succeeded_sources=5,
            admission_max_recent_failure_rate=0.2,
            admission_min_avg_parse_confidence=0.8,
            admission_max_zero_program_rate=0.3,
        ),
    )
    assert decision.admitted is True
    assert decision.reason is None
