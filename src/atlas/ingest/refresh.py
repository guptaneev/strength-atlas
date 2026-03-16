from __future__ import annotations

from sqlalchemy.orm import Session

from atlas.browser_use.client import BrowserUseClient
from atlas.db.models import Source
from atlas.ingest.extraction import extract_url


async def refresh_source(session: Session, client: BrowserUseClient, source_id: int) -> None:
    source = session.get(Source, source_id)
    if not source:
        raise ValueError(f"Source {source_id} not found")
    await extract_url(session=session, client=client, url=source.url, source=source)
