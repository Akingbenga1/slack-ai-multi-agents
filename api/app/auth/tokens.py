from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

import jwt
from fastapi import HTTPException, status

from api.app.settings import Settings

RoleName = Literal["platform_owner", "org_admin"]


@dataclass
class AuthPrincipal:
    sub: str
    email: str
    role: RoleName
    tenant_id: Optional[str]
    all_access: bool


def create_access_token(
    *,
    settings: Settings,
    sub: str,
    email: str,
    role: RoleName,
    tenant_id: Optional[str],
    expires_minutes: int = 60 * 12,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "role": role,
        "tenant_id": tenant_id,
        "all_access": role == "platform_owner",
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _principal_from_payload(payload: dict[str, Any]) -> AuthPrincipal:
    role = payload.get("role")
    if role not in ("platform_owner", "org_admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid role claim")
    return AuthPrincipal(
        sub=str(payload.get("sub", "")),
        email=str(payload.get("email", "")),
        role=role,
        tenant_id=payload.get("tenant_id"),
        all_access=role == "platform_owner",
    )


def decode_access_token(token: str, settings: Settings) -> AuthPrincipal:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return _principal_from_payload(payload)


def refresh_access_token(token: str, settings: Settings, *, max_stale_days: int = 30) -> str:
    """Mint a new JWT from a valid (possibly expired) bearer token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    exp = payload.get("exp")
    if exp is not None:
        exp_dt = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=max_stale_days)
        if exp_dt < stale_cutoff:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token too old to refresh",
                headers={"WWW-Authenticate": "Bearer"},
            )

    principal = _principal_from_payload(payload)
    return create_access_token(
        settings=settings,
        sub=principal.sub,
        email=principal.email,
        role=principal.role,
        tenant_id=principal.tenant_id,
    )
