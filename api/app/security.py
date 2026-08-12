"""Startup security checks and shared constants."""

from __future__ import annotations

from api.app.constants import DEFAULT_JWT_SECRET
from api.app.settings import Settings


def validate_security_settings(settings: Settings) -> None:
    """
    Fail fast when obviously unsafe settings are used outside development.

    Raises ``RuntimeError`` when misconfigured for production/staging.
    """
    env = (settings.app_env or "development").strip().lower()
    secret = (settings.jwt_secret or "").strip()

    if env in ("production", "staging"):
        if not secret or secret == DEFAULT_JWT_SECRET:
            raise RuntimeError(
                "JWT_SECRET must be set to a strong random value when APP_ENV is "
                f"{env!r} (default dev secret is not allowed)"
            )
        if len(secret) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 characters in production/staging")

    if env == "production" and settings.debug_endpoints_enabled:
        raise RuntimeError("DEBUG_ENDPOINTS_ENABLED must be false when APP_ENV is production")


def cors_allow_origins(settings: Settings) -> list[str]:
    raw = (settings.cors_origins or "").strip()
    if not raw:
        return ["http://localhost:3000"]
    return [part.strip() for part in raw.split(",") if part.strip()]
