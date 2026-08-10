from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.app.agent.routes import router as agent_router
from api.app.admin.routes import router as admin_router
from api.app.auth.routes import router as auth_router
from api.app.billing.routes import router as billing_router
from api.app.governance.routes import router as usage_router
from api.app.health import run_deep_health
from api.app.jobs.routes import router as jobs_router
from api.app.logging_config import configure_logging, get_logger
from api.app.middleware import TenantContextMiddleware, TenantRateLimitMiddleware
from api.app.settings import get_settings
from api.app.slack.routes import router as slack_router
from api.app.tenant import get_client_id
from api.app.uploads.routes import router as uploads_router
from api.app.workflows.routes import router as workflows_router

configure_logging()
logger = get_logger("api")

app = FastAPI(title="Client Slack AI Agents API", version="0.1.0")
# Starlette: last added runs first. Order: CORS → Tenant → RateLimit → routes.
app.add_middleware(TenantRateLimitMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(billing_router)
app.include_router(usage_router)
app.include_router(agent_router)
app.include_router(jobs_router)
app.include_router(slack_router)
app.include_router(uploads_router)
app.include_router(workflows_router)


@app.get("/health")
def health() -> dict:
    """Deep health: Postgres, Redis, Qdrant, TEI."""
    settings = get_settings()
    payload = run_deep_health(settings)
    logger.info("health_check status=%s", payload["status"])
    return payload


@app.get("/debug/tenant")
def debug_tenant() -> dict[str, str | None]:
    """Dev helper to verify tenant middleware."""
    return {"client_id": get_client_id()}
