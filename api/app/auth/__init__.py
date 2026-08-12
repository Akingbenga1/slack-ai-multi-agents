"""Auth package — JWT principal + IdentityProvider Strategy (Sprint 36)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from api.app.auth.provider import IdentityProvider, get_identity_provider
from api.app.auth.tokens import AuthPrincipal, create_access_token, decode_access_token

if TYPE_CHECKING:
    from api.app.auth.credentials_adapter import CredentialsIdentityProvider

__all__ = [
    "AuthPrincipal",
    "CredentialsIdentityProvider",
    "IdentityProvider",
    "create_access_token",
    "decode_access_token",
    "get_identity_provider",
]


def __getattr__(name: str):
    # Lazy: credentials adapter imports membership; membership imports tokens.
    if name == "CredentialsIdentityProvider":
        from api.app.auth.credentials_adapter import CredentialsIdentityProvider

        return CredentialsIdentityProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
