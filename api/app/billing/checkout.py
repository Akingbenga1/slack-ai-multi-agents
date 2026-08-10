"""Stripe Checkout Session helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from api.app.billing.customers import BillingError, ensure_billing_customer
from api.app.billing.stripe_client import configure_stripe, stripe_configured
from api.app.settings import Settings


def create_checkout_session(
    db: Session,
    *,
    tenant_id: UUID | str,
    email: str | None,
    settings: Settings,
) -> str:
    """
    Ensure Stripe customer, create a subscription Checkout Session, return hosted URL.
    """
    if not stripe_configured(settings):
        raise BillingError("STRIPE_SECRET_KEY is not set")
    price_id = (settings.stripe_price_id or "").strip()
    if not price_id:
        raise BillingError("STRIPE_PRICE_ID is not set")

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
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=row.stripe_customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{web}/app/billing?checkout=success",
            cancel_url=f"{web}/app/billing?checkout=cancel",
            client_reference_id=str(row.tenant_id),
            metadata={
                "tenant_id": str(row.tenant_id),
                "client_id": str(row.tenant_id),
            },
            subscription_data={
                "metadata": {
                    "tenant_id": str(row.tenant_id),
                    "client_id": str(row.tenant_id),
                },
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise BillingError(f"Stripe Checkout Session.create failed: {exc}") from exc

    url = getattr(session, "url", None) or (session.get("url") if isinstance(session, dict) else None)
    if not url:
        raise BillingError("Stripe Checkout Session returned no url")
    return str(url)
