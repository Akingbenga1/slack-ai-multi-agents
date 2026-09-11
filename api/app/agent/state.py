"""Shared agent typing helpers."""

from __future__ import annotations

from typing import Literal

# Vendor-neutral tiers — adapters map to concrete model ids
ModelTier = Literal["fast", "capable"]
