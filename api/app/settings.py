from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings. Secrets optional until later sprints."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core services
    database_url: str = "postgresql+psycopg://csa:csa@localhost:5433/csa"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "knowledge"
    tei_url: str = "http://localhost:8080"
    # Must match Compose TEI `--model-id` (BAAI/bge-small-en-v1.5 → 384-dim)
    embedding_model_id: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # Public / auth
    public_base_url: str = "http://localhost:8000"
    # Next.js origin for Stripe Checkout / Portal return URLs (Sprint 11)
    web_app_url: str = "http://localhost:3000"
    jwt_secret: str = "dev-change-me-use-at-least-32-chars!!"

    # Uploads (Sprint 8) — relative paths resolve from process cwd (repo root)
    upload_dir: str = "data/uploads"

    # LLM / agent (Sprint 13+)
    anthropic_api_key: str = ""
    anthropic_model_haiku: str = "claude-3-5-haiku-latest"
    anthropic_model_sonnet: str = "claude-sonnet-4-20250514"
    anthropic_max_tokens: int = 1024
    agent_retrieve_top_k: int = 8
    # Drop weak neighbors below this cosine score (hard hedge when none remain)
    agent_min_score: float = 0.70
    # memory | postgres — Postgres tables created via checkpointer.setup()
    agent_checkpointer: str = "postgres"
    # mcp | direct — tools node default is MCP client (stdio); direct = in-process
    agent_retrieve_backend: str = "mcp"
    # Optional override for stdio MCP launch (default: current python -m mcp_server)
    agent_mcp_command: str = ""
    agent_mcp_args: str = ""

    # Slack (Sprint 4+)
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""
    # Sprint 9.4 — Beat interval for live history sync dispatcher (seconds)
    slack_history_sync_interval_seconds: float = 3600.0
    # Sprint 17.3 — Beat intervals for recurring report dispatchers (seconds)
    recurring_report_daily_interval_seconds: float = 86400.0
    recurring_report_weekly_interval_seconds: float = 604800.0

    # Stripe (Sprint 11+)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # Governance (Sprint 12+) — per-tenant gateway RPM
    rate_limit_enabled: bool = True
    rate_limit_rpm: int = 60

    # Demo seed hardening (Sprint 22.1) — laptop demo without live Stripe/OAuth
    demo_activate_plan: bool = False
    demo_slack_team_id: str = ""
    demo_slack_bot_token: str = ""
    demo_report_channel_id: str = ""

    @property
    def upload_dir_path(self):
        from pathlib import Path

        return Path(self.upload_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
