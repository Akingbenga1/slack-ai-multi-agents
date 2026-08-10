"""Create / retrieve Stripe Customers linked 1:1 to tenants."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.app.billing.stripe_client import configure_stripe, stripe_configured
from api.app.db.models import BillingCustomer, Tenant, User
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.billing.customers")


class BillingError(RuntimeError):
    """Billing domain error (missing tenant, Stripe failure, etc.)."""


def get_billing_customer(db: Session, tenant_id: UUID | str) -> BillingCustomer | None:
    tid = UUID(str(tenant_id))
    return db.scalar(select(BillingCustomer).where(BillingCustomer.tenant_id == tid))


def _default_email_for_tenant(db: Session, tenant_id: UUID) -> str | None:
    """Prefer an org membership user's email; fall back to None."""
    from api.app.db.models import Membership

    membership = db.scalar(
        select(Membership).where(Membership.tenant_id == tenant_id).limit(1)
    )
    if membership is None:
        return None
    user = db.get(User, membership.user_id)
    return user.email if user else None


def ensure_billing_customer(
    db: Session,
    *,
    tenant_id: UUID | str,
    email: Optional[str] = None,
    settings: Settings | None = None,
    create_stripe: bool = True,
) -> BillingCustomer:
    """
    Ensure a `billing_customers` row for the tenant; create/retrieve Stripe Customer when configured.

    Idempotent: reuses existing `stripe_customer_id`. When Stripe is not configured and
    `create_stripe` is True, still ensures the local row (`plan_status=inactive`) without
    a Stripe id — Checkout/Portal will fail closed until keys are set.
    """
    settings = settings or get_settings()
    tid = UUID(str(tenant_id))
    tenant = db.get(Tenant, tid)
    if tenant is None:
        raise BillingError(f"Tenant not found: {tid}")

    row = get_billing_customer(db, tid)
    if row is None:
        from api.app.billing.plans import INACTIVE_ENTITLEMENTS

        row = BillingCustomer(
            tenant_id=tid,
            plan_status="inactive",
            entitlements=dict(INACTIVE_ENTITLEMENTS),
            meta={},
        )
        db.add(row)
        db.flush()
        logger.info("billing_customer_row_created tenant_id=%s", tid)

    if row.stripe_customer_id:
        return row

    if not create_stripe:
        return row

    if not stripe_configured(settings):
        logger.warning(
            "stripe_not_configured tenant_id=%s — billing row without stripe_customer_id",
            tid,
        )
        return row

    customer_email = (email or _default_email_for_tenant(db, tid) or "").strip() or None
    stripe_id = _create_stripe_customer(
        settings=settings,
        tenant=tenant,
        email=customer_email,
    )
    row.stripe_customer_id = stripe_id
    meta = dict(row.meta or {})
    meta["stripe_email"] = customer_email
    row.meta = meta
    db.add(row)
    db.flush()
    logger.info(
        "stripe_customer_created tenant_id=%s stripe_customer_id=%s",
        tid,
        stripe_id,
    )
    return row


def _create_stripe_customer(
    *,
    settings: Settings,
    tenant: Tenant,
    email: str | None,
) -> str:
    import stripe

    configure_stripe(settings)
    params: dict = {
        "name": tenant.name,
        "metadata": {
            "tenant_id": str(tenant.id),
            "tenant_slug": tenant.slug,
            "client_id": str(tenant.id),
        },
    }
    if email:
        params["email"] = email
    try:
        customer = stripe.Customer.create(**params)
    except Exception as exc:  # noqa: BLE001 — surface as BillingError
        raise BillingError(f"Stripe Customer.create failed: {exc}") from exc
    cid = getattr(customer, "id", None) or (customer.get("id") if isinstance(customer, dict) else None)
    if not cid:
        raise BillingError("Stripe Customer.create returned no id")
    return str(cid)
