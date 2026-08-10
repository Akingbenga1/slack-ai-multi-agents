"""Small retry helper for transient outbound HTTP / RPC failures (Sprint 22.5)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from api.app.logging_config import get_logger

logger = get_logger("api.http_retry")

T = TypeVar("T")


def is_transient_http_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def call_with_retries(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    should_retry: Callable[[BaseException], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    backoff_base: float = 0.5,
    label: str = "request",
) -> T:
    """
    Call ``fn`` up to ``max_retries + 1`` times.

    Retries when ``should_retry(exc)`` is true (default: connection-ish errors).
    Backoff: ``backoff_base * 2**attempt`` seconds (capped at 8s).
    """
    last: BaseException | None = None
    attempts = max(0, int(max_retries)) + 1
    for attempt in range(attempts):
        try:
            return fn()
        except BaseException as exc:  # noqa: BLE001 — re-raise non-retryable
            last = exc
            retryable = should_retry(exc) if should_retry else _default_transient(exc)
            if not retryable or attempt >= attempts - 1:
                raise
            delay = min(8.0, float(backoff_base) * (2**attempt))
            logger.warning(
                "%s failed attempt=%s/%s retry_in=%.1fs err=%s",
                label,
                attempt + 1,
                attempts,
                delay,
                exc,
            )
            sleep(delay)
    assert last is not None
    raise last


def _default_transient(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "WriteTimeout",
        "PoolTimeout",
        "NetworkError",
        "RemoteProtocolError",
        "TimeoutException",
    }:
        return True
    # httpx / requests style
    if "Timeout" in name or "Connection" in name:
        return True
    return False
