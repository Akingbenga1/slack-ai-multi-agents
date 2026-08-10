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


def decode_access_token(token: str, settings: Settings) -> AuthPrincipal:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    role = payload.get("role")
    if role not in ("platform_owner", "org_admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid role claim")

    return AuthPrincipal(
        sub=str(payload.get("sub", "")),
        email=str(payload.get("email", "")),
        role=role,
        tenant_id=payload.get("tenant_id"),
        all_access=bool(payload.get("all_access")) or role == "platform_owner",
    )
