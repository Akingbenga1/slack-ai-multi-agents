from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from api.app.governance.rate_limit import (
    check_tenant_rate_limit,
    decision_to_body,
    is_rate_limit_exempt,
    rate_limit_headers,
)
from api.app.settings import get_settings
from api.app.tenant import CLIENT_ID_HEADER, clear_client_id, get_client_id, set_client_id


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Attach `client_id` from `X-Client-Id` for the duration of the request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        raw = request.headers.get(CLIENT_ID_HEADER)
        set_client_id(raw)
        try:
            response = await call_next(request)
        finally:
            clear_client_id()
        if raw:
            response.headers[CLIENT_ID_HEADER] = raw.strip()
        return response


class TenantRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Enforce per-tenant RPM when request context has a `client_id` (X-Client-Id).

    Must run inside TenantContextMiddleware so context is set.
    Routes that resolve tenant later (Slack Events) call `check_tenant_rate_limit` themselves.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if is_rate_limit_exempt(path):
            return await call_next(request)

        client_id = get_client_id()
        if not client_id:
            return await call_next(request)

        decision = check_tenant_rate_limit(client_id, settings=get_settings())
        if not decision.allowed:
            return JSONResponse(
                status_code=429,
                content=decision_to_body(decision),
                headers=rate_limit_headers(decision),
            )

        response = await call_next(request)
        if not decision.skipped:
            for key, value in rate_limit_headers(decision).items():
                response.headers[key] = value
        return response
