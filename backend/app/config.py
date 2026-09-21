"""Central configuration. All credentials are read from the environment only."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "DRISHTI Narrative Intelligence API"
    api_prefix: str = "/api"

    # sqlite fallback keeps the prototype runnable without Docker/PostgreSQL
    database_url: str = "postgresql+psycopg://drishti:drishti_local_dev@localhost:5432/drishti"

    cors_origins: str = "http://localhost:8080,http://localhost:5173,http://127.0.0.1:8080"

    # Platform adapters (never exposed to the frontend)
    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    telegram_webhook_secret: str = ""
    telegram_poll_seconds: int = 60
    # MTProto (Telethon) abstraction - optional, kept separate from the Bot API path
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_session: str = ""
    x_bearer_token: str = ""
    x_client_id: str = ""
    x_client_secret: str = ""

    # Ingestion / scheduler
    ingestion_enabled: bool = False
    scheduler_interval: str = "manual"  # manual | 5m | 15m | hourly
    live_connector_test: bool = False
    adapter_max_retries: int = 2

    # Analyst assistant LLM provider abstraction
    llm_provider: str = "auto"  # auto | openai | gemini | local
    llm_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Demographic privacy threshold (percentage points)
    min_cohort_percentage: float = 5.0

    seed_demo_data: bool = True

    # ---------------------------------------------------------------- auth
    # Local JWT authentication. Enforcement is opt-in so the offline demo can
    # be shown without a login step; set AUTH_REQUIRED=true to protect the API.
    auth_required: bool = False
    jwt_secret: str = "drishti-local-development-secret-change-me"
    jwt_expires_minutes: int = 720
    # First administrator is provisioned from the environment, never hard-coded.
    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "Administrator"

    # ---------------------------------------------------------------- RAG
    embedding_model_name: str = "drishti-local-hashing-v1"
    embedding_dimensions: int = 256
    assistant_rate_limit_per_minute: int = 20

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_llm_key(self) -> str:
        return self.llm_api_key or self.openai_api_key or self.gemini_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
