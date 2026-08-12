"""PaymentProvider factory smoke (Sprint 34.1)."""

from __future__ import annotations

import pytest

from api.app.billing.provider import get_payment_provider
from api.app.billing.stripe_adapter import StripePaymentProvider
from api.app.settings import Settings


def test_factory_defaults_to_stripe():
    provider = get_payment_provider(Settings(payment_provider="stripe"))
    assert isinstance(provider, StripePaymentProvider)
    assert provider.name == "stripe"


def test_factory_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown PAYMENT_PROVIDER"):
        get_payment_provider(Settings(payment_provider="square"))


def test_factory_paypal_not_implemented():
    with pytest.raises(ValueError, match="PayPal"):
        get_payment_provider(Settings(payment_provider="paypal"))


def test_stripe_not_configured_without_key():
    provider = get_payment_provider(Settings(stripe_secret_key="", payment_provider="stripe"))
    assert provider.is_configured() is False
