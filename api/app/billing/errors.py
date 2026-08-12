"""Billing domain errors."""

from __future__ import annotations


class BillingError(RuntimeError):
    """Billing domain error (missing tenant, gateway failure, etc.)."""
