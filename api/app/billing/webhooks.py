"""Payment webhook HTTP helpers + thin Stripe aliases (Task 11.4 / Sprint 34.3).

Product routes call ``PaymentProvider.verify_webhook`` / ``handle_webhook``.
``construct_stripe_event`` / ``handle_stripe_event`` remain for tests and docs.
Event mapping lives on the Stripe adapter; apply uses Template Method.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from api.app.settings import Settings


class WebhookError(RuntimeError):
    """Webhook processing / verification failure."""


def construct_stripe_event(payload: bytes, sig_header: str, settings: Settings) -> Any:
    """Verify signature and return a Stripe Event (delegates to Stripe adapter)."""
    from api.app.billing.provider import get_payment_provider

    return get_payment_provider(settings).verify_webhook(payload, sig_header)


def handle_stripe_event(db: Session, event: Any) -> dict[str, Any]:
    """Apply plan changes via Stripe adapter map + shared Template Method apply."""
    from api.app.billing.provider import get_payment_provider
    from api.app.settings import get_settings

    return get_payment_provider(get_settings()).handle_webhook(db, event)
