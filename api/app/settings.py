from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from api.app.constants import DEFAULT_JWT_SECRET

AppEnv = Literal["development", "staging", "production"]


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

    # LLM / agent (Sprint 13+; Sprint 33 provider factory)
    # anthropic | ollama | stub — offline/tests use stub (not empty Anthropic key)
    llm_provider: Literal["anthropic", "ollama", "stub"] = "anthropic"
    # Anthropic-adapter secrets (names kept for existing deploys)
    anthropic_api_key: str = ""
    anthropic_model_haiku: str = "claude-3-5-haiku-latest"
    anthropic_model_sonnet: str = "claude-sonnet-4-20250514"
    anthropic_max_tokens: int = 1024
    # Ollama / OpenAI-compatible adapter (base URL + tier tags)
    ollama_url: str = "http://localhost:11434"
    ollama_model_fast: str = "llama3.2"
    ollama_model_capable: str = "llama3.1"
    ollama_max_tokens: int = 1024
    agent_retrieve_top_k: int = 8
    # Drop weak neighbors below this cosine score (hard hedge when none remain)
    agent_min_score: float = 0.70
    # memory | postgres — Postgres tables created via checkpointer.setup()
    agent_checkpointer: str = "postgres"
    # mcp | direct — tools node default is MCP client; direct = in-process retrieval
    agent_retrieve_backend: str = "mcp"
    # in_process (API/worker default) | stdio (external / Inspector-style)
    agent_mcp_transport: str = "in_process"
    # Optional override for stdio MCP launch (default: current python -m mcp_server)
    agent_mcp_command: str = ""
    agent_mcp_args: str = ""
    # Hard deadline for one MCP tool call (in-process or stdio)
    agent_mcp_timeout_seconds: float = 60.0
    # Cap retrieve/tool top-k to bound Qdrant payload memory
    agent_retrieve_max_top_k: int = 32
    # Keep at most this many checkpointed messages per thread (human+AI turns)
    agent_max_checkpoint_messages: int = 40

    # Slack (Sprint 4+)
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_signing_secret: str = ""
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

    @property
    def upload_dir_path(self):
        from pathlib import Path

        return Path(self.upload_dir)


@lru_cache
def get_settings() -> Settings:
    return Settings()
