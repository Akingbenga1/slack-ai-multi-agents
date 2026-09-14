from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from api.app.constants import DEFAULT_JWT_SECRET

AppEnv = Literal["development", "staging", "production"]
SlackEventsTransport = Literal["http", "socket"]


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
    # Job queue (Sprint 38) — Strategy factory; Celery is the first adapter
    # Validated in get_job_queue (celery|rq|dramatiq); str so unknown values surface there
    # REDIS_URL stays the Celery broker — do not rename
    job_queue: str = "celery"
    # Vector store (Sprint 35) — Strategy factory; Qdrant is the first adapter
    # Validated in get_vector_store (qdrant|pgvector); str so unknown values surface there
    vector_store: str = "qdrant"
    # Qdrant-adapter secrets (names kept for existing deploys)
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "knowledge"
    # Embedding provider (Sprint 35) — Strategy factory; TEI is the first adapter
    # Validated in get_embedding_provider (tei|ollama|openai)
    embedding_provider: str = "tei"
    # TEI-adapter secrets (names kept for existing deploys)
    tei_url: str = "http://localhost:8080"
    # Must match Compose TEI `--model-id` (BAAI/bge-small-en-v1.5 → 384-dim)
    embedding_model_id: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # Public / auth
    public_base_url: str = "http://localhost:8000"
    # Next.js origin for Stripe Checkout / Portal return URLs (Sprint 11)
    web_app_url: str = "http://localhost:3000"
    app_env: AppEnv = "development"
    # Identity provider (Sprint 36) — Strategy factory; credentials is the demo default
    # Validated in get_identity_provider (credentials|oidc|saml|google|microsoft)
    identity_provider: str = "credentials"
    jwt_secret: str = DEFAULT_JWT_SECRET
    # Optional separate key for encrypting Slack bot tokens (defaults to jwt_secret)
    token_encryption_key: str = ""
    # Comma-separated browser origins for CORS (Sprint 30 security)
    cors_origins: str = "http://localhost:3000"
    # Expose /debug/* routes (must be false in production)
    debug_endpoints_enabled: bool = True

    # Blob store (Sprint 37) — Strategy factory; local disk is the first adapter
    # Validated in get_blob_store (local|s3); str so unknown values surface there
    blob_store: str = "local"
    # Local-adapter root (Sprint 8 name kept for existing deploys)
    # Relative paths resolve from process cwd (repo root)
    upload_dir: str = "data/uploads"

    # LLM / agent — role-named config (provider id validated in llm_config registry)
    # Registered ids: stub | anthropic | ollama | openai_compat
    llm_provider: str = "anthropic"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_fast: str = ""
    llm_model_capable: str = ""
    llm_max_tokens: int = 0
    # Legacy adapter secrets (aliases; prefer LLM_* vars above)
    anthropic_api_key: str = ""
    anthropic_model_haiku: str = "claude-3-5-haiku-latest"
    anthropic_model_sonnet: str = "claude-sonnet-4-20250514"
    anthropic_max_tokens: int = 1024
    # Ollama / OpenAI-compatible adapter (base URL + tier tags)
    ollama_url: str = "http://localhost:11434"
    ollama_model_fast: str = "llama3.2"
    ollama_model_capable: str = "llama3.1"
    ollama_max_tokens: int = 1024
    # Hard deadline for one MCP tool call
    agent_mcp_timeout_seconds: float = 60.0

    # Slack (Sprint 4+)
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""
    # Event transport: http (Events API + tunnel) | socket (Socket Mode, no events tunnel)
    slack_events_transport: SlackEventsTransport = "http"
    # App-level token (xapp-…) — required when slack_events_transport=socket
    slack_app_token: str = ""
    # Sprint 9.4 — Beat interval for live history sync dispatcher (seconds)
    slack_history_sync_interval_seconds: float = 3600.0
    # Bound in-memory backlog while syncing a channel (messages per ingest batch)
    slack_sync_ingest_batch_size: int = 100
    # Sprint 17.3 — Beat intervals for recurring report dispatchers (seconds)
    recurring_report_daily_interval_seconds: float = 86400.0
    recurring_report_weekly_interval_seconds: float = 604800.0

    # Payment gateway (Sprint 34) — Strategy factory; Stripe is the first adapter
    # Validated in get_payment_provider (stripe|paypal); str so unknown values surface there
    payment_provider: str = "stripe"
    # Stripe-adapter secrets (names kept for existing deploys)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # Governance (Sprint 12+) — per-tenant gateway RPM
    rate_limit_enabled: bool = True
    rate_limit_rpm: int = 60
    # When false, Redis errors deny requests instead of failing open
    rate_limit_fail_open: bool = True

    # Agent run workspaces (isolated per plan step; inputs copied in, never
    # mutated in place). Relative paths resolve from the project root.
    agent_workspace_root: str = "data/workspaces"
    # Retain workspace directories after a run for debugging and trace replay.
    agent_workspace_keep: bool = True

    # CLI tool execution (Sprint 47)
    cli_tools_enabled: bool = True
    cli_tools_timeout_seconds: int = 120
    cli_tools_max_output_bytes: int = 1_000_000
    # Host CLI check/install control plane (not used by the harness runtime)
    cli_host_install_enabled: bool = True
    cli_host_install_timeout_seconds: int = 300
    mcp_host_check_timeout_seconds: float = 20.0
    # MCP Connect/OAuth (remote HTTP) — redirect uses public_base_url by default
    mcp_oauth_client_id: str = ""
    mcp_oauth_client_secret: str = ""
    mcp_oauth_redirect_path: str = "/mcp-servers/oauth/callback"
    mcp_oauth_scopes: str = ""

    # System-wide tool discovery (not tenant-scoped)
    # CLI: portable tldr SQLite DB (relative paths resolve from project root)
    discovery_cli_db_path: str = "tldr_pages.db"
    discovery_cli_search_limit: int = 15
    # Celery Beat interval for upstream tldr → SQLite refresh (default weekly)
    discovery_cli_update_interval_seconds: float = 604800.0
    # Official MCP Registry base URL — set via DISCOVERY_MCP_SERVICE_URL (no code default)
    discovery_mcp_service_url: str = ""
    # Reserved for a future HTTP-tools discovery route
    discovery_http_service_url: str = ""
    discovery_timeout_seconds: float = 45.0
    discovery_mcp_search_limit: int = 10
    discovery_mcp_cache_ttl_seconds: float = 300.0


    # Demo seed hardening (Sprint 22.1) — laptop demo without live Stripe/OAuth
    demo_activate_plan: bool = False
    demo_slack_team_id: str = ""
    demo_slack_bot_token: str = ""
    demo_report_channel_id: str = ""

    # Sprint 32.3 — policy guardrail for admin plan waivers (None = env default)
    allow_plan_waivers: bool | None = None

    def plan_waivers_permitted(self) -> bool:
        """True when operators may activate plans without Stripe."""
        if self.allow_plan_waivers is not None:
            return self.allow_plan_waivers
        return self.app_env == "development"

    def slack_socket_mode_enabled(self) -> bool:
        """True when Socket Mode transport is selected and app token is set."""
        return (
            self.slack_events_transport == "socket"
            and bool((self.slack_app_token or "").strip())
        )

    @property
    def upload_dir_path(self):
        from pathlib import Path

        return Path(self.upload_dir)

    @property
    def discovery_cli_db_path_resolved(self):
        """Absolute path to the portable tldr CLI discovery SQLite file."""
        from pathlib import Path

        path = Path(self.discovery_cli_db_path)
        if path.is_absolute():
            return path
        # api/app/settings.py → project root is parents[2]
        return Path(__file__).resolve().parents[2] / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
