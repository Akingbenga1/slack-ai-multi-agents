"""Auth IdentityProvider isolation (Sprint 36.3)."""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_APP = _REPO / "api" / "app"

# Token-issue product surface must not own the password-table path.
_FORBIDDEN = re.compile(
    r"\b(resolve_login_principal|verify_password|hash_password|pwd_context)\b",
)

_ISOLATED_MODULES = (
    _APP / "auth" / "routes.py",
)


def test_token_route_has_no_password_table_helpers():
    for path in _ISOLATED_MODULES:
        text = path.read_text(encoding="utf-8")
        hit = _FORBIDDEN.search(text)
        assert hit is None, f"{path.name} mentions {hit.group(0)!r}"


def test_token_route_uses_identity_provider():
    routes = (_APP / "auth" / "routes.py").read_text(encoding="utf-8")
    assert "get_identity_provider" in routes
    assert "idp.verify(" in routes or ".verify(" in routes
    assert "create_access_token" in routes


def test_demo_default_is_credentials():
    from api.app.settings import Settings

    assert Settings().identity_provider == "credentials"
