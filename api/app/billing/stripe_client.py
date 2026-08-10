"""Stripe SDK configuration helpers."""

from __future__ import annotations

import stripe

from api.app.settings import Settings


class StripeNotConfiguredError(RuntimeError):
    """Raised when STRIPE_SECRET_KEY is missing and a live Stripe call is required."""


def configure_stripe(settings: Settings) -> str:
    """Set stripe.api_key from settings; return the secret key."""
    key = (settings.stripe_secret_key or "").strip()
    if not key:
        raise StripeNotConfiguredError(
            "STRIPE_SECRET_KEY is not set — add a Stripe test secret to .env"
        )
    stripe.api_key = key
    return key


def stripe_configured(settings: Settings) -> bool:
    return bool((settings.stripe_secret_key or "").strip())
