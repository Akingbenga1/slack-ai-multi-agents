"""Slack signing-secret verification (HTTP Events)."""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException, Request, status


async def verify_slack_signature(request: Request, signing_secret: str) -> bytes:
    """Validate Slack request signature; return raw body bytes."""
    if not signing_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SLACK_SIGNING_SECRET not configured",
        )

    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not timestamp or not signature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Slack signature headers")

    try:
        ts = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid timestamp") from exc

    if abs(time.time() - ts) > 60 * 5:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Stale Slack request")

    basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected = f"v0={digest}"
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Slack signature")

    return body
