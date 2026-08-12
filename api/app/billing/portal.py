"""Customer portal session helpers — product facade over ``PaymentProvider``."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from api.app.billing.customers import ensure_billing_customer
from api.app.billing.errors import BillingError
from api.app.billing.provider import get_payment_provider
from api.app.settings import Settings


def create_portal_session(
    db: Session,
    *,
    tenant_id: UUID | str,
    email: str | None,
    settings: Settings,
) -> str:
    """Ensure gateway customer exists, create a self-serve portal session, return URL."""
    provider = get_payment_provider(settings)
    if not provider.is_configured():
        raise BillingError("STRIPE_SECRET_KEY is not set")

    row = ensure_billing_customer(
        db,
        tenant_id=tenant_id,
        email=email,
        settings=settings,
        create_external=True,
    )
    external_id = row.external_customer_id
    if not external_id:
        raise BillingError("Payment customer could not be created")

    web = (settings.web_app_url or "http://localhost:3000").rstrip("/")
    return provider.create_portal_url(
        external_customer_id=external_id,
        return_url=f"{web}/app/billing",
    )
