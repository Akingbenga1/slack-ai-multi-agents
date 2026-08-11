"""Per-tenant request rate limits (RPM) via Redis."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from redis import Redis

from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.governance.rate_limit")

# Paths that never consume tenant RPM (webhooks, probes, OpenAPI, Slack Events).
RATE_LIMIT_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/billing/webhooks",
    "/slack",
    "/auth",
)


@dataclass(frozen=True)
class RateLimitDecision:
    """Result of a rate-limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: int  # unix seconds when the current window ends
    retry_after: int  # seconds until client may retry (0 if allowed)
    client_id: str
    skipped: bool = False  # True when limit not applied (disabled / no redis / etc.)


def _window_start(now: float | None = None) -> int:
    t = int(now if now is not None else time.time())
    return t - (t % 60)


def _redis_key(client_id: str, window_start: int) -> str:
    return f"rl:rpm:{client_id}:{window_start}"


def check_tenant_rate_limit(
    client_id: str,
    *,
    settings: Settings | None = None,
    redis_client: Redis | None = None,
    now: float | None = None,
) -> RateLimitDecision:
    """
    Fixed-window RPM check for one tenant (`client_id`).

    Uses Redis INCR + EXPIRE on `rl:rpm:{client_id}:{window}`.
    On Redis errors, fails open (allowed=True, skipped=True).
    """
    cfg = settings or get_settings()
    cid = (client_id or "").strip()
    limit = max(1, int(cfg.rate_limit_rpm))
    window = _window_start(now)
    reset_at = window + 60

    if not cfg.rate_limit_enabled:
        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=limit,
            reset_at=reset_at,
            retry_after=0,
            client_id=cid,
            skipped=True,
        )

    if not cid:
        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=limit,
            reset_at=reset_at,
            retry_after=0,
            client_id="",
            skipped=True,
        )

    owned = False
    client = redis_client
    try:
        if client is None:
            client = Redis.from_url(cfg.redis_url, socket_connect_timeout=2)
            owned = True
        key = _redis_key(cid, window)
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 70)  # slightly past window for late readers
        count, _ = pipe.execute()
        count_i = int(count)
        remaining = max(0, limit - count_i)
        if count_i > limit:
            retry = max(1, reset_at - int(now if now is not None else time.time()))
            logger.warning(
                "rate_limit_exceeded client_id=%s count=%s limit=%s retry_after=%s",
                cid,
                count_i,
                limit,
                retry,
            )
            return RateLimitDecision(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=reset_at,
                retry_after=retry,
                client_id=cid,
            )
        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=0,
            client_id=cid,
        )
    except Exception as exc:  # noqa: BLE001 — fail open
        logger.error("rate_limit_redis_error client_id=%s err=%s", cid, exc)
        return RateLimitDecision(
            allowed=True,
            limit=limit,
            remaining=limit,
            reset_at=reset_at,
            retry_after=0,
            client_id=cid,
            skipped=True,
        )
    finally:
        if owned and client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass


def rate_limit_headers(decision: RateLimitDecision) -> dict[str, str]:
    """Standard-ish rate limit response headers."""
    headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
        "X-RateLimit-Reset": str(decision.reset_at),
    }
    if not decision.allowed and decision.retry_after > 0:
        headers["Retry-After"] = str(decision.retry_after)
    return headers


def is_rate_limit_exempt(path: str) -> bool:
    p = path or ""
    return any(p == prefix or p.startswith(prefix + "/") for prefix in RATE_LIMIT_EXEMPT_PREFIXES)


def decision_to_body(decision: RateLimitDecision) -> dict[str, Any]:
    return {
        "detail": "rate_limit_exceeded",
        "client_id": decision.client_id,
        "limit": decision.limit,
        "retry_after": decision.retry_after,
    }
