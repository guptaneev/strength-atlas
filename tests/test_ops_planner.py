from atlas.db.models import Domain, Source
from atlas.ops.planner import load_runnable_domains, plan_sources_for_domain


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _ScalarResult(self._values)


class _QueueSession:
    def __init__(self, results):
        self._results = list(results)

    def execute(self, _stmt):
        if not self._results:
            raise AssertionError("unexpected execute call")
        return _Result(self._results.pop(0))


def test_load_runnable_domains_respects_allowlist_and_pause() -> None:
    rows = [
        Domain(id=1, domain="ok.com", allowlisted=True, paused=False),
        Domain(id=2, domain="paused.com", allowlisted=True, paused=True),
        Domain(id=3, domain="noallow.com", allowlisted=False, paused=False),
    ]
    session = _QueueSession([rows])
    runnable, issues = load_runnable_domains(
        session,
        requested_domains=["ok.com", "paused.com", "missing.com", "noallow.com"],
    )
    assert [d.domain for d in runnable] == ["ok.com"]
    assert [i.reason for i in issues] == ["domain_paused", "domain_not_found", "domain_not_allowlisted"]


def test_plan_sources_prioritizes_pending_and_respects_cap() -> None:
    domain_row = Domain(id=10, domain="example.com", allowlisted=True, paused=False)
    pending = [
        Source(id=1, url="https://a", canonical_url="https://a", domain_id=10, status="pending"),
        Source(id=2, url="https://b", canonical_url="https://b", domain_id=10, status="pending"),
    ]
    session = _QueueSession([pending])
    planned = plan_sources_for_domain(
        session,
        domain_row=domain_row,
        per_domain_limit=2,
        global_remaining=10,
    )
    assert [p.source_id for p in planned] == [1, 2]
    assert [p.mode for p in planned] == ["extract_pending", "extract_pending"]


def test_plan_sources_fills_remaining_with_empty_program_sources() -> None:
    domain_row = Domain(id=10, domain="example.com", allowlisted=True, paused=False)
    pending = [
        Source(id=1, url="https://a", canonical_url="https://a", domain_id=10, status="pending"),
    ]
    empty = [
        Source(id=3, url="https://c", canonical_url="https://c", domain_id=10, status="succeeded", latest_document_id=99),
    ]
    session = _QueueSession([pending, empty])
    planned = plan_sources_for_domain(
        session,
        domain_row=domain_row,
        per_domain_limit=2,
        global_remaining=10,
    )
    assert [p.source_id for p in planned] == [1, 3]
    assert [p.mode for p in planned] == ["extract_pending", "refresh_empty"]
