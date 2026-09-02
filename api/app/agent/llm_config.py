"""Role-named LLM configuration and provider registry (adapter edge).

Resolves neutral env vars with legacy aliases. Maps provider id → adapter shape.
Core agent code reads only ``LlmRuntimeConfig`` — not vendor-specific settings fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.app.settings import Settings

# Provider id → adapter shape (not per-brand adapters).
ADAPTER_SHAPE_STUB = "stub"
ADAPTER_SHAPE_ANTHROPIC = "anthropic_messages"
ADAPTER_SHAPE_OPENAI_COMPAT = "openai_compat"

PROVIDER_REGISTRY: dict[str, str] = {
    "stub": ADAPTER_SHAPE_STUB,
    "anthropic": ADAPTER_SHAPE_ANTHROPIC,
    "ollama": ADAPTER_SHAPE_OPENAI_COMPAT,
    "openai_compat": ADAPTER_SHAPE_OPENAI_COMPAT,
}


def registered_provider_ids() -> tuple[str, ...]:
    return tuple(sorted(PROVIDER_REGISTRY.keys()))


@dataclass(frozen=True)
class LlmRuntimeConfig:
    """Resolved chat backend connection — provider-neutral."""

    provider_id: str
    adapter_shape: str
    api_key: str
    base_url: str
    model_fast: str
    model_capable: str
    max_tokens: int


def _non_empty(*values: str | None) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def resolve_llm_runtime_config(settings: Settings) -> LlmRuntimeConfig:
    """Build runtime config from neutral env vars, falling back to legacy names."""
    provider_id = (settings.llm_provider or "anthropic").strip().lower()
    shape = PROVIDER_REGISTRY.get(provider_id)
    if shape is None:
        registered = ", ".join(registered_provider_ids())
        raise ValueError(
            f"Unknown LLM_PROVIDER={provider_id!r}; registered: {registered}"
        )

    api_key = _non_empty(settings.llm_api_key)
    base_url = _non_empty(settings.llm_base_url)
    model_fast = _non_empty(settings.llm_model_fast)
    model_capable = _non_empty(settings.llm_model_capable)

    if shape == ADAPTER_SHAPE_ANTHROPIC:
        api_key = api_key or _non_empty(settings.anthropic_api_key)
        model_fast = model_fast or _non_empty(settings.anthropic_model_haiku)
        model_capable = model_capable or _non_empty(settings.anthropic_model_sonnet)
    elif shape == ADAPTER_SHAPE_OPENAI_COMPAT:
        base_url = base_url or _non_empty(settings.ollama_url)
        model_fast = model_fast or _non_empty(settings.ollama_model_fast)
        model_capable = model_capable or _non_empty(settings.ollama_model_capable)

    if shape == ADAPTER_SHAPE_OPENAI_COMPAT and not base_url:
        base_url = "http://localhost:11434"

    max_tokens = int(settings.llm_max_tokens or 0)
    if max_tokens <= 0:
        max_tokens = int(
            settings.anthropic_max_tokens or settings.ollama_max_tokens or 1024
        )

    config = LlmRuntimeConfig(
        provider_id=provider_id,
        adapter_shape=shape,
        api_key=api_key,
        base_url=base_url.rstrip("/") if base_url else "",
        model_fast=model_fast,
        model_capable=model_capable,
        max_tokens=max_tokens,
    )
    _validate_runtime_config(config)
    return config


def _validate_runtime_config(config: LlmRuntimeConfig) -> None:
    if config.adapter_shape == ADAPTER_SHAPE_STUB:
        return
    if config.adapter_shape == ADAPTER_SHAPE_ANTHROPIC:
        if not config.api_key:
            raise ValueError(
                "LLM API key is empty; set LLM_API_KEY (or legacy ANTHROPIC_API_KEY) "
                "or use LLM_PROVIDER=stub"
            )
        if not config.model_fast or not config.model_capable:
            raise ValueError(
                "LLM model tiers are required; set LLM_MODEL_FAST and LLM_MODEL_CAPABLE "
                "(or legacy ANTHROPIC_MODEL_* vars)"
            )
        return
    if config.adapter_shape == ADAPTER_SHAPE_OPENAI_COMPAT:
        if not config.base_url:
            raise ValueError(
                "LLM base URL is empty; set LLM_BASE_URL (or legacy OLLAMA_URL)"
            )
        if not config.model_fast or not config.model_capable:
            raise ValueError(
                "LLM model tiers are required; set LLM_MODEL_FAST and LLM_MODEL_CAPABLE "
                "(or legacy OLLAMA_MODEL_* vars)"
            )
        return
    raise ValueError(f"unsupported adapter shape: {config.adapter_shape!r}")
