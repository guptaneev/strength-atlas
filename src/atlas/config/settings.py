from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ATLAS_", extra="ignore")

    # Supabase
    supabase_url: Optional[str] = None
    supabase_service_key: Optional[str] = None
    supabase_publishable_key: Optional[str] = None
    supabase_storage_bucket: Optional[str] = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: Optional[str] = None
    supabase_jwks_url: Optional[str] = None
    supabase_auth_timeout_seconds: int = Field(default=10, ge=1, le=60)

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
    reranker_model_path: Optional[str] = None
    reranker_candidate_depth: int = Field(default=50, ge=1, le=200)
    reranker_max_length: int = Field(default=256, ge=32, le=1024)
    reranker_batch_size: int = Field(default=16, ge=1, le=128)
    reranker_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    reranker_max_workers: int = Field(default=1, ge=1, le=4)
    reranker_failure_cooldown_seconds: int = Field(default=60, ge=0, le=3600)
    reranker_model_version: str = "strength-atlas-cross-encoder-authoritative-v1"
    reranker_weights_sha256: Optional[str] = None
    reranker_model_url: Optional[str] = None
    reranker_archive_sha256: Optional[str] = None

    # API runtime
    app_env: str = "development"
    api_docs_enabled: bool = True
    cors_allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    trusted_hosts: str = "localhost,127.0.0.1"
    enforce_https_redirect: bool = False
    request_max_body_bytes: int = Field(default=131072, ge=1024, le=1048576)
    ask_request_timeout_seconds: int = Field(default=30, ge=1, le=120)

    # Ask quota and anti-abuse
    ask_lifetime_limit: int = Field(default=5, ge=1, le=10000)
    ask_ip_rate_limit_window_seconds: int = Field(default=60, ge=1, le=86400)
    ask_ip_rate_limit_max_requests: int = Field(default=30, ge=1, le=10000)
    ask_user_rate_limit_window_seconds: int = Field(default=60, ge=1, le=86400)
    ask_user_rate_limit_max_requests: int = Field(default=20, ge=1, le=10000)
    ask_contact_cta_url: str = "mailto:support@strengthatlas.app"

    def csv_items(self, value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
