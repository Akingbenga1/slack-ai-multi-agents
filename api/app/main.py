from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.agent.cli_host_routes import router as cli_host_router
from api.app.agent.routes import router as agent_router
from api.app.agent.tool_routes import router as tools_router
from api.app.admin.routes import router as admin_router
from api.app.auth.deps import get_current_principal
from api.app.auth.routes import router as auth_router
from api.app.auth.tokens import AuthPrincipal
from api.app.billing.routes import router as billing_router
from api.app.discovery.routes import router as discovery_router
from api.app.governance.routes import router as usage_router
from api.app.health import run_deep_health
from api.app.jobs.routes import router as jobs_router
from api.app.logging_config import configure_logging, get_logger
from api.app.middleware import TenantContextMiddleware, TenantRateLimitMiddleware
from api.app.mcp_servers.admin_routes import router as admin_mcp_servers_router
from api.app.mcp_servers.routes import router as mcp_servers_router
from api.app.security import cors_allow_origins, validate_security_settings
from api.app.settings import Settings, get_settings
from api.app.slack.routes import router as slack_router
from api.app.tenant import get_client_id
from api.app.ingestion.routes import router as ingestion_router
from api.app.uploads.routes import router as uploads_router
from api.app.workflows.routes import router as workflows_router
from api.app.tenant_files.routes import router as tenant_files_router
from api.app.skills.routes import router as skills_router

configure_logging()
logger = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    validate_security_settings(settings)
    logger.info("security_settings_ok app_env=%s", settings.app_env)

    if settings.slack_events_transport == "socket":
        if settings.slack_socket_mode_enabled():
            from api.app.slack.socket_mode import start_socket_mode

            start_socket_mode(settings)
            logger.info("slack_events_transport=socket")
        else:
            logger.warning(
                "slack_events_transport=socket but SLACK_APP_TOKEN is missing; "
                "Socket Mode listener not started"
            )

    try:
        yield
    finally:
        if settings.slack_events_transport == "socket":
            from api.app.slack.socket_mode import stop_socket_mode

            stop_socket_mode()


app = FastAPI(title="Client Slack AI Agents API", version="0.1.0", lifespan=lifespan)
# Starlette: last added runs first. Order: CORS → Tenant → RateLimit → routes.
app.add_middleware(TenantRateLimitMiddleware)
app.add_middleware(TenantContextMiddleware)
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins(_settings),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(admin_mcp_servers_router, prefix="/admin")
app.include_router(billing_router)
app.include_router(usage_router)
app.include_router(agent_router)
app.include_router(cli_host_router)
app.include_router(mcp_servers_router)
app.include_router(tools_router)
app.include_router(discovery_router)
app.include_router(jobs_router)
app.include_router(slack_router)
app.include_router(uploads_router)
app.include_router(ingestion_router)
app.include_router(workflows_router)
app.include_router(tenant_files_router)
app.include_router(skills_router)


@app.get("/health")
def health() -> dict:
    """Deep health: Postgres, Redis, Qdrant, TEI."""
    settings = get_settings()
    payload = run_deep_health(settings)
    logger.info("health_check status=%s", payload["status"])
    return payload


if _settings.debug_endpoints_enabled:

    @app.get("/debug/tenant")
    def debug_tenant(
        _: AuthPrincipal = Depends(get_current_principal),
    ) -> dict[str, str | None]:
        """Dev helper to verify tenant middleware (auth required)."""
        return {"client_id": get_client_id()}
