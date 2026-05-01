from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.api.errors import QuotaExceededError
from atlas.config.settings import get_settings
from atlas.db.models import AskQuotaUsage


@dataclass(frozen=True)
class QuotaSnapshot:
    limit: int
    used: int
    remaining: int
    can_ask: bool


def get_quota_snapshot(session: Session, *, user_id: str) -> QuotaSnapshot:
    settings = get_settings()
    limit = max(0, int(settings.ask_lifetime_limit))
    row = session.get(AskQuotaUsage, user_id)
    used = int(row.used_count if row else 0)
    remaining = max(0, limit - used)
    return QuotaSnapshot(limit=limit, used=used, remaining=remaining, can_ask=remaining > 0)


def consume_ask_quota(session: Session, *, user_id: str) -> QuotaSnapshot:
    settings = get_settings()
    limit = max(0, int(settings.ask_lifetime_limit))
    now = datetime.now(UTC)
    row = session.execute(
        select(AskQuotaUsage).where(AskQuotaUsage.user_id == user_id).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        row = AskQuotaUsage(user_id=user_id, used_count=0, created_at=now, updated_at=now)
        session.add(row)
        session.flush()

    used = int(row.used_count or 0)
    if used >= limit:
        remaining = 0
        raise QuotaExceededError(
            limit=limit,
            used=used,
            remaining=remaining,
            contact_url=settings.ask_contact_cta_url,
        )

    row.used_count = used + 1
    row.updated_at = now
    session.flush()
    remaining = max(0, limit - row.used_count)
    return QuotaSnapshot(limit=limit, used=row.used_count, remaining=remaining, can_ask=remaining > 0)
