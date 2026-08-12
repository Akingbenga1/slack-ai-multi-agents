"""Identity Strategy + Factory (Sprint 36).

``POST /auth/token`` and NextAuth know only ``IdentityProvider.verify`` →
``AuthPrincipal``. Password-table / future OIDC·SAML details live in adapters;
``get_identity_provider`` selects by ``IDENTITY_PROVIDER``.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from api.app.auth.tokens import AuthPrincipal
from api.app.settings import Settings, get_settings


class IdentityProvider(Protocol):
    """Vendor-neutral identity verification surface."""

    @property
    def name(self) -> str:
        """Adapter id (e.g. ``credentials``)."""
        ...

    def verify(
        self,
        db: Session,
        *,
        email: str,
        password: str = "",
    ) -> AuthPrincipal | None:
        """Verify an identity assertion → product ``AuthPrincipal``, or None."""
        ...


def get_identity_provider(settings: Settings | None = None) -> IdentityProvider:
    """Factory: select IdP by ``IDENTITY_PROVIDER`` (default ``credentials``)."""
    settings = settings or get_settings()
    name = (settings.identity_provider or "credentials").strip().lower()
    if name == "credentials":
        from api.app.auth.credentials_adapter import CredentialsIdentityProvider

        return CredentialsIdentityProvider()
    if name in ("oidc", "saml", "google", "microsoft"):
        raise ValueError(
            f"{name} identity adapter is not implemented — set IDENTITY_PROVIDER=credentials "
            "(documented extension only; no OIDC/SAML env keys this sprint)"
        )
    raise ValueError(
        f"Unknown IDENTITY_PROVIDER={name!r}; expected credentials|oidc|saml|google|microsoft"
    )
