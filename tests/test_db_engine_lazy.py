from types import SimpleNamespace

import pytest

import atlas.db.engine as engine


def test_import_does_not_require_database_url() -> None:
    # Module import already succeeded by virtue of running this test.
    assert hasattr(engine, "SessionLocal")


def test_sessionlocal_raises_only_on_use_when_database_url_missing(monkeypatch) -> None:
    engine.get_engine.cache_clear()
    monkeypatch.setattr("atlas.db.engine.get_settings", lambda: SimpleNamespace(database_url=None))
    with pytest.raises(RuntimeError, match="ATLAS_DATABASE_URL is required"):
        engine.SessionLocal()
