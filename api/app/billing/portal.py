"""Stripe Customer Portal session helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from api.app.billing.customers import BillingError, ensure_billing_customer
from api.app.billing.stripe_client import configure_stripe, stripe_configured
from api.app.settings import Settings


def create_portal_session(
    db: Session,
    *,
    tenant_id: UUID | str,
    email: str | None,
    settings: Settings,
) -> str:
    """Ensure Stripe customer exists, create a Billing Portal session, return URL."""
    if not stripe_configured(settings):
        raise BillingError("STRIPE_SECRET_KEY is not set")

    row = ensure_billing_customer(
        db,
        tenant_id=tenant_id,
        email=email,
        settings=settings,
        create_stripe=True,
    )
    if not row.stripe_customer_id:
        raise BillingError("Stripe customer could not be created")

    web = (settings.web_app_url or "http://localhost:3000").rstrip("/")
    configure_stripe(settings)

    import stripe

    try:
        session = stripe.billing_portal.Session.create(
            customer=row.stripe_customer_id,
            return_url=f"{web}/app/billing",
        )
    except Exception as exc:  # noqa: BLE001
        raise BillingError(f"Stripe Portal Session.create failed: {exc}") from exc

    url = getattr(session, "url", None) or (session.get("url") if isinstance(session, dict) else None)
    if not url:
        raise BillingError("Stripe Portal Session returned no url")
    return str(url)
