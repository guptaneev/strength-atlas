from datetime import UTC, datetime, timedelta

from atlas.db.models import Source
from atlas.ops.backlog import build_backlog_report


class _Result:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _Session:
    def __init__(self, values):
        self._values = values

    def execute(self, _stmt):
        return _Result(self._values)


def test_build_backlog_report_groups_and_marks_stale() -> None:
    now = datetime.now(UTC)
    values = [
        (
            Source(id=1, canonical_url="https://a", domain_id=1, status="pending"),
            "example.com",
        ),
        (
            Source(id=2, canonical_url="https://b", domain_id=1, status="succeeded", last_crawled_at=now - timedelta(days=30)),
            "example.com",
        ),
        (
            Source(id=3, canonical_url="https://c", domain_id=2, status="failed"),
            "other.com",
        ),
    ]
    report = build_backlog_report(
        _Session(values),
        stale_after_days=14,
        pending_sample_size=3,
    )
    assert report["totals"]["domains_count"] == 2
    assert report["totals"]["pending"] == 1
    assert report["totals"]["stale_succeeded"] == 1


def test_build_backlog_report_domain_filter() -> None:
    values = [
        (Source(id=1, canonical_url="https://a", domain_id=1, status="pending"), "example.com"),
        (Source(id=2, canonical_url="https://b", domain_id=2, status="pending"), "other.com"),
    ]
    report = build_backlog_report(_Session(values), domains=["example.com"])
    assert report["totals"]["domains_count"] == 1
    assert report["by_domain"][0]["domain"] == "example.com"
