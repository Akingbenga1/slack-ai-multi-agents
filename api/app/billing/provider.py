"""Payment gateway Strategy + Factory (Sprint 34).

Billing product code knows only ``PaymentProvider`` — ensure customer,
checkout URL, portal URL, webhook verify + map. Vendor SDKs live in
adapters; ``get_payment_provider`` selects by ``PAYMENT_PROVIDER``.
Webhook apply uses Template Method in ``webhook_pipeline``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from api.app.settings import Settings, get_settings

if TYPE_CHECKING:
    from api.app.billing.webhook_pipeline import MappedPlanEvent


class PaymentProvider(Protocol):
    """Vendor-neutral payment gateway surface."""

    @property
    def name(self) -> str:
        """Adapter id (e.g. ``stripe``) — also used as ``plan_source`` for gateway updates."""
        ...

    def is_configured(self) -> bool:
        """True when adapter secrets are present for live gateway calls."""
        ...

    def ensure_customer(
        self,
        *,
        tenant_id: UUID,
        tenant_name: str,
        tenant_slug: str,
        email: str | None,
        existing_external_id: str | None = None,
    ) -> str:
        """Return external customer id; create at the gateway when missing."""
        ...

    def create_checkout_url(
        self,
        *,
        external_customer_id: str,
        tenant_id: UUID,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Hosted checkout / subscription pay URL."""
        ...

    def create_portal_url(
        self,
        *,
        external_customer_id: str,
        return_url: str,
    ) -> str:
        """Customer self-serve portal URL (payment method / cancel)."""
        ...

    def verify_webhook(self, payload: bytes, signature_header: str) -> Any:
        """Verify signature; return a vendor event object."""
        ...

    def map_webhook_event(self, event: Any) -> Optional["MappedPlanEvent"]:
        """Adapter-owned map: vendor event → ``MappedPlanEvent`` (or None to ignore)."""
        ...

    def handle_webhook(self, db: Session, event: Any) -> dict[str, Any]:
        """Convenience: map + shared apply (Template Method steps 2–3)."""
        ...


def get_payment_provider(settings: Settings | None = None) -> PaymentProvider:
    """Factory: select payment adapter by ``PAYMENT_PROVIDER`` (default ``stripe``)."""
    settings = settings or get_settings()
    name = (settings.payment_provider or "stripe").strip().lower()
    if name == "stripe":
        from api.app.billing.stripe_adapter import StripePaymentProvider

        return StripePaymentProvider(settings)
    if name == "paypal":
        raise ValueError(
            "PayPal payment adapter is not implemented — set PAYMENT_PROVIDER=stripe "
            "(documented extension only)"
        )
    raise ValueError(f"Unknown PAYMENT_PROVIDER={name!r}; expected stripe|paypal")
