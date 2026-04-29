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
    discovery_max_candidates_per_run: int = 200
    discovery_blocked_path_tokens: str = (
        "wp-admin,wp-json,feed,cart,checkout,my-account,privacy-policy,terms,cookie-policy,login,register,author,tag"
    )

    # Ops automation defaults
    ops_per_domain_limit: int = 10
    ops_global_limit: int = 50
    ops_failure_rate_threshold: float = 0.35
    ops_runs_ledger_path: str = "var/atlas/runs.jsonl"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
