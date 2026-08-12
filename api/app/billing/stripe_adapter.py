"""Stripe SDK Adapter for ``PaymentProvider`` (Sprint 34)."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.billing.errors import BillingError
from api.app.billing.plans import (
    plan_status_from_stripe,
    resolve_tenant_id_from_checkout,
    resolve_tenant_id_from_subscription,
)
from api.app.billing.stripe_client import configure_stripe, stripe_configured
from api.app.billing.webhook_pipeline import MappedPlanEvent, handle_mapped_webhook
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.billing.stripe_adapter")


class StripePaymentProvider:
    """Stripe Checkout / Customer Portal / webhook adapter."""

    name = "stripe"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def is_configured(self) -> bool:
        return stripe_configured(self.settings)

    def ensure_customer(
        self,
        *,
        tenant_id: UUID,
        tenant_name: str,
        tenant_slug: str,
        email: str | None,
        existing_external_id: str | None = None,
    ) -> str:
        if existing_external_id:
            return existing_external_id
        if not self.is_configured():
            raise BillingError("STRIPE_SECRET_KEY is not set")

        import stripe

        configure_stripe(self.settings)
        params: dict[str, Any] = {
            "name": tenant_name,
            "metadata": {
                "tenant_id": str(tenant_id),
                "tenant_slug": tenant_slug,
                "client_id": str(tenant_id),
            },
        }
        if email:
            params["email"] = email
        try:
            customer = stripe.Customer.create(**params)
        except Exception as exc:  # noqa: BLE001
            raise BillingError(f"Stripe Customer.create failed: {exc}") from exc
        cid = getattr(customer, "id", None) or (
            customer.get("id") if isinstance(customer, dict) else None
        )
        if not cid:
            raise BillingError("Stripe Customer.create returned no id")
        return str(cid)

    def create_checkout_url(
        self,
        *,
        external_customer_id: str,
        tenant_id: UUID,
        success_url: str,
        cancel_url: str,
    ) -> str:
        if not self.is_configured():
            raise BillingError("STRIPE_SECRET_KEY is not set")
        price_id = (self.settings.stripe_price_id or "").strip()
        if not price_id:
            raise BillingError("STRIPE_PRICE_ID is not set")

        import stripe

        configure_stripe(self.settings)
        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=external_customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=str(tenant_id),
                metadata={
                    "tenant_id": str(tenant_id),
                    "client_id": str(tenant_id),
                },
                subscription_data={
                    "metadata": {
                        "tenant_id": str(tenant_id),
                        "client_id": str(tenant_id),
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001
            raise BillingError(f"Stripe Checkout Session.create failed: {exc}") from exc

        url = getattr(session, "url", None) or (
            session.get("url") if isinstance(session, dict) else None
        )
        if not url:
            raise BillingError("Stripe Checkout Session returned no url")
        return str(url)

    def create_portal_url(
        self,
        *,
        external_customer_id: str,
        return_url: str,
    ) -> str:
        if not self.is_configured():
            raise BillingError("STRIPE_SECRET_KEY is not set")

        import stripe

        configure_stripe(self.settings)
        try:
            session = stripe.billing_portal.Session.create(
                customer=external_customer_id,
                return_url=return_url,
            )
        except Exception as exc:  # noqa: BLE001
            raise BillingError(f"Stripe Portal Session.create failed: {exc}") from exc

        url = getattr(session, "url", None) or (
            session.get("url") if isinstance(session, dict) else None
        )
        if not url:
            raise BillingError("Stripe Portal Session returned no url")
        return str(url)

    def verify_webhook(self, payload: bytes, signature_header: str) -> Any:
        from api.app.billing.webhooks import WebhookError

        secret = (self.settings.stripe_webhook_secret or "").strip()
        if not secret:
            raise WebhookError("STRIPE_WEBHOOK_SECRET is not set")
        if not signature_header:
            raise WebhookError("Missing Stripe-Signature header")

        import stripe

        configure_stripe(self.settings)
        try:
            return stripe.Webhook.construct_event(payload, signature_header, secret)
        except ValueError as exc:
            raise WebhookError(f"Invalid webhook payload: {exc}") from exc
        except stripe.error.SignatureVerificationError as exc:
            raise WebhookError(f"Invalid Stripe signature: {exc}") from exc

    def map_webhook_event(self, event: Any) -> Optional[MappedPlanEvent]:
        """Stripe event → ``MappedPlanEvent`` (adapter-owned map)."""
        event_type = _attr(event, "type") or ""
        data_object = _nested(event, "data", "object")

        if event_type == "checkout.session.completed":
            return self._map_checkout_completed(event_type, data_object)
        if event_type == "customer.subscription.updated":
            return self._map_subscription_updated(event_type, data_object)
        if event_type == "customer.subscription.deleted":
            return self._map_subscription_deleted(event_type, data_object)

        logger.info("stripe_webhook_ignored type=%s", event_type)
        return None

    def handle_webhook(self, db: Session, event: Any) -> dict[str, Any]:
        return handle_mapped_webhook(db, self, event)

    def _map_checkout_completed(
        self, event_type: str, session_obj: Any
    ) -> MappedPlanEvent:
        mode = _attr(session_obj, "mode")
        if mode and mode != "subscription":
            return MappedPlanEvent(
                event_type=event_type,
                handled=False,
                skip_reason="not_subscription_mode",
            )
        customer_id = _attr(session_obj, "customer")
        subscription_id = _attr(session_obj, "subscription")
        return MappedPlanEvent(
            event_type=event_type,
            plan_status="active",
            tenant_id=resolve_tenant_id_from_checkout(session_obj),
            external_customer_id=str(customer_id) if customer_id else None,
            external_subscription_id=str(subscription_id) if subscription_id else None,
            extra_meta={"last_checkout_session_id": _attr(session_obj, "id")},
        )

    def _map_subscription_updated(
        self, event_type: str, sub_obj: Any
    ) -> MappedPlanEvent:
        status = _attr(sub_obj, "status")
        sub_id = _attr(sub_obj, "id")
        customer_id = _attr(sub_obj, "customer")
        return MappedPlanEvent(
            event_type=event_type,
            plan_status=plan_status_from_stripe(str(status) if status else None),
            tenant_id=resolve_tenant_id_from_subscription(sub_obj),
            external_customer_id=str(customer_id) if customer_id else None,
            external_subscription_id=str(sub_id) if sub_id else None,
            extra_meta={"stripe_subscription_status": status},
        )

    def _map_subscription_deleted(
        self, event_type: str, sub_obj: Any
    ) -> MappedPlanEvent:
        sub_id = _attr(sub_obj, "id")
        customer_id = _attr(sub_obj, "customer")
        return MappedPlanEvent(
            event_type=event_type,
            plan_status="inactive",
            tenant_id=resolve_tenant_id_from_subscription(sub_obj),
            external_customer_id=str(customer_id) if customer_id else None,
            external_subscription_id=str(sub_id) if sub_id else None,
            clear_subscription=True,
            extra_meta={"stripe_subscription_status": "canceled"},
        )


def _attr(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _nested(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
        cur = _attr(cur, key)
        if cur is None:
            return None
    return cur
