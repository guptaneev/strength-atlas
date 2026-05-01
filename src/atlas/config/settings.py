from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ATLAS_")

    # Supabase
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_publishable_key: Optional[str] = None
    supabase_storage_bucket: Optional[str] = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: Optional[str] = None
    supabase_jwks_url: Optional[str] = None
    supabase_auth_timeout_seconds: int = 10

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

    # Retrieval debugging
    retrieval_debug_trace_path: str = "var/atlas/retrieval-debug.jsonl"

    # API runtime
    app_env: str = "development"
    api_docs_enabled: bool = True
    cors_allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    trusted_hosts: str = "localhost,127.0.0.1"
    enforce_https_redirect: bool = False
    request_max_body_bytes: int = 131072
    ask_request_timeout_seconds: int = 30

    # Ask quota and anti-abuse
    ask_lifetime_limit: int = 5
    ask_ip_rate_limit_window_seconds: int = 60
    ask_ip_rate_limit_max_requests: int = 30
    ask_user_rate_limit_window_seconds: int = 60
    ask_user_rate_limit_max_requests: int = 20
    ask_contact_cta_url: str = "mailto:support@strengthatlas.app"

    def csv_items(self, value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
