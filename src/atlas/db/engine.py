from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from atlas.config.settings import get_settings


def get_engine():
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("ATLAS_DATABASE_URL is required")
    return create_engine(settings.database_url, pool_pre_ping=True)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
