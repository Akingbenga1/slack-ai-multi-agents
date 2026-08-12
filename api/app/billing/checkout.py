"""Checkout session helpers — product facade over ``PaymentProvider``."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from api.app.billing.customers import ensure_billing_customer
from api.app.billing.errors import BillingError
from api.app.billing.provider import get_payment_provider
from api.app.settings import Settings


def create_checkout_session(
    db: Session,
    *,
    tenant_id: UUID | str,
    email: str | None,
    settings: Settings,
) -> str:
    """
    Ensure gateway customer, create a subscription checkout session, return hosted URL.
    """
    provider = get_payment_provider(settings)
    if not provider.is_configured():
        raise BillingError("STRIPE_SECRET_KEY is not set")
    # Fail closed on missing price before any gateway customer create (Stripe adapter secret)
    if provider.name == "stripe" and not (settings.stripe_price_id or "").strip():
        raise BillingError("STRIPE_PRICE_ID is not set")

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
    return provider.create_checkout_url(
        external_customer_id=external_id,
        tenant_id=row.tenant_id,
        success_url=f"{web}/app/billing?checkout=success",
        cancel_url=f"{web}/app/billing?checkout=cancel",
    )
