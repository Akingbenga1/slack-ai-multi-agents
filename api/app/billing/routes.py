"""Billing HTTP routes — customers, checkout, portal, webhooks (Sprint 11)."""

from __future__ import annotations

from typing import Annotated, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.app.auth.deps import require_tenant_access
from api.app.auth.tenant_resolve import resolve_tenant_uuid_for_principal
from api.app.auth.tokens import AuthPrincipal
from api.app.billing.checkout import create_checkout_session
from api.app.billing.customers import BillingError, ensure_billing_customer, get_billing_customer
from api.app.billing.portal import create_portal_session
from api.app.billing.webhooks import WebhookError, construct_stripe_event, handle_stripe_event
from api.app.db.session import get_db
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.billing.routes")

router = APIRouter(prefix="/billing", tags=["billing"])


class BillingCustomerResponse(BaseModel):
    tenant_id: str
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    plan_status: str
    entitlements: dict[str, bool]


class SessionUrlResponse(BaseModel):
    url: str


def _customer_response(row) -> BillingCustomerResponse:
    ents = row.entitlements or {}
    return BillingCustomerResponse(
        tenant_id=str(row.tenant_id),
        stripe_customer_id=row.stripe_customer_id,
        stripe_subscription_id=row.stripe_subscription_id,
        plan_status=row.plan_status,
        entitlements={k: bool(v) for k, v in ents.items()},
    )


def _resolve_tenant_id(principal: AuthPrincipal) -> UUID:
    return resolve_tenant_uuid_for_principal(principal)


@router.post("/customers/ensure", response_model=BillingCustomerResponse)
def ensure_customer(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BillingCustomerResponse:
    """Create/retrieve Stripe customer for the current tenant (org signup / pre-checkout)."""
    tid = _resolve_tenant_id(principal)
    try:
        row = ensure_billing_customer(
            db,
            tenant_id=tid,
            email=principal.email,
            settings=settings,
        )
        db.commit()
        db.refresh(row)
    except BillingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _customer_response(row)


@router.get("/customers/me", response_model=BillingCustomerResponse)
def get_my_customer(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
) -> BillingCustomerResponse:
    tid = _resolve_tenant_id(principal)
    row = get_billing_customer(db, tid)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No billing customer")
    return _customer_response(row)


@router.post("/checkout-session", response_model=SessionUrlResponse)
def checkout_session(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionUrlResponse:
    """Create a Stripe Checkout Session for the tenant subscription price."""
    tid = _resolve_tenant_id(principal)
    try:
        url = create_checkout_session(
            db,
            tenant_id=tid,
            email=principal.email,
            settings=settings,
        )
        db.commit()
    except BillingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SessionUrlResponse(url=url)


@router.post("/portal-session", response_model=SessionUrlResponse)
def portal_session(
    principal: Annotated[AuthPrincipal, Depends(require_tenant_access)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionUrlResponse:
    """Create a Stripe Customer Portal session for payment method / cancel."""
    tid = _resolve_tenant_id(principal)
    try:
        url = create_portal_session(
            db,
            tenant_id=tid,
            email=principal.email,
            settings=settings,
        )
        db.commit()
    except BillingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SessionUrlResponse(url=url)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """
    Stripe webhook endpoint (no JWT).

    Configure Dashboard → `{PUBLIC_BASE_URL}/billing/webhooks/stripe`.
    Events: checkout.session.completed, customer.subscription.updated|deleted.
    """
    payload = await request.body()
    sig = request.headers.get("stripe-signature") or request.headers.get("Stripe-Signature") or ""
    try:
        event = construct_stripe_event(payload, sig, settings)
    except WebhookError as exc:
        msg = str(exc)
        code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "STRIPE_WEBHOOK_SECRET" in msg
            else status.HTTP_401_UNAUTHORIZED
        )
        raise HTTPException(status_code=code, detail=msg) from exc

    try:
        result = handle_stripe_event(db, event)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — return 500 so Stripe retries
        db.rollback()
        logger.exception("stripe_webhook_handler_failed type=%s", getattr(event, "type", None))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook handler failed",
        ) from exc

    logger.info(
        "stripe_webhook_ok type=%s handled=%s",
        result.get("type") or getattr(event, "type", None),
        result.get("handled"),
    )
    return {"received": True, **result}
