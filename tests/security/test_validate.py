"""Security settings validation."""

from __future__ import annotations

import pytest

from api.app.constants import DEFAULT_JWT_SECRET
from api.app.security import validate_security_settings
from api.app.settings import Settings


def test_production_rejects_default_jwt_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_security_settings(
            Settings(app_env="production", jwt_secret=DEFAULT_JWT_SECRET)
        )


def test_production_rejects_debug_endpoints():
    with pytest.raises(RuntimeError, match="DEBUG_ENDPOINTS_ENABLED"):
        validate_security_settings(
            Settings(
                app_env="production",
                jwt_secret="x" * 32,
                debug_endpoints_enabled=True,
            )
        )


def test_development_allows_default_secret():
    validate_security_settings(Settings(app_env="development", jwt_secret=DEFAULT_JWT_SECRET))
