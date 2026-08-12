"""Credentials IdentityProvider adapter (Sprint 36).

Email + password against Postgres memberships. Owns the password-table path so
token issue / NextAuth do not.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from api.app.auth.tokens import AuthPrincipal
from api.app.membership import resolve_login_principal


class CredentialsIdentityProvider:
    """Demo-default IdP — verify email/password → ``AuthPrincipal``."""

    @property
    def name(self) -> str:
        return "credentials"

    def verify(
        self,
        db: Session,
        *,
        email: str,
        password: str = "",
    ) -> AuthPrincipal | None:
        login = resolve_login_principal(db, email=email, password=password)
        if login is None:
            return None
        return AuthPrincipal(
            sub=login.sub,
            email=login.email,
            role=login.role,
            tenant_id=login.tenant_id,
            all_access=login.all_access,
        )
