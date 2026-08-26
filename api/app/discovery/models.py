"""HTTP request/response models for discovery routes."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from api.app.discovery.base import ToolKind


class KindStatus(BaseModel):
    configured: bool
    env_key: str


class DiscoveryStatusResponse(BaseModel):
    kinds: dict[str, KindStatus]


class DiscoverySearchBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)


class DiscoveredToolResponse(BaseModel):
    id: str
    name: str
    summary: str
    source: str
    kind: ToolKind
    # Present for CLI hits: registry-aligned {command, args, subcommands{purpose,usage}}
    config: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


class DiscoverySearchResponse(BaseModel):
    kind: ToolKind
    query: str
    tools: list[DiscoveredToolResponse]
