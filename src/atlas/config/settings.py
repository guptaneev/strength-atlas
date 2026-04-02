from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ATLAS_")

    # Supabase
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_storage_bucket: Optional[str] = None

    # Database
    database_url: Optional[str] = None

    # Browser Use
    browser_use_api_key: Optional[str] = None
    browser_use_poll_timeout_seconds: int = 300
    browser_use_extract_model_primary: str = "bu-mini"
    browser_use_extract_model_fallback: str = "bu-max"
    max_crawl_retries: int = 2


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
