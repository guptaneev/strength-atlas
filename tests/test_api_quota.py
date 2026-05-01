from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from atlas.api.errors import QuotaExceededError
from atlas.api.quota import consume_ask_quota, get_quota_snapshot
from atlas.db.models import AskQuotaUsage


def _session() -> Session:
    engine = create_engine("sqlite://")
    AskQuotaUsage.__table__.create(bind=engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return maker()


def test_consume_ask_quota_blocks_at_limit(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.quota.get_settings",
        lambda: SimpleNamespace(ask_lifetime_limit=5, ask_contact_cta_url="mailto:test@example.com"),
    )
    session = _session()
    for _ in range(5):
        snapshot = consume_ask_quota(session, user_id="u1")
        session.commit()
    assert snapshot.used == 5
    with pytest.raises(QuotaExceededError):
        consume_ask_quota(session, user_id="u1")


def test_get_quota_snapshot_reads_existing_usage(monkeypatch) -> None:
    monkeypatch.setattr(
        "atlas.api.quota.get_settings",
        lambda: SimpleNamespace(ask_lifetime_limit=5, ask_contact_cta_url="mailto:test@example.com"),
    )
    session = _session()
    session.add(AskQuotaUsage(user_id="u2", used_count=3))
    session.commit()
    snapshot = get_quota_snapshot(session, user_id="u2")
    assert snapshot.used == 3
    assert snapshot.remaining == 2
