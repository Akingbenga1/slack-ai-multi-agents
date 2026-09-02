"""Tests for role-named LLM configuration and provider registry."""

from __future__ import annotations

import pytest

from api.app.agent.llm_config import (
    registered_provider_ids,
    resolve_llm_runtime_config,
)
from api.app.settings import Settings


def test_registered_provider_ids_includes_openai_compat():
    assert "openai_compat" in registered_provider_ids()
    assert "anthropic" in registered_provider_ids()
    assert "ollama" in registered_provider_ids()
    assert "stub" in registered_provider_ids()


def test_resolve_neutral_openai_compat_vars():
    settings = Settings(
        llm_provider="openai_compat",
        llm_base_url="https://example.test",
        llm_api_key="sk-remote",
        llm_model_fast="fast-model",
        llm_model_capable="capable-model",
        llm_max_tokens=256,
    )
    config = resolve_llm_runtime_config(settings)
    assert config.provider_id == "openai_compat"
    assert config.adapter_shape == "openai_compat"
    assert config.base_url == "https://example.test"
    assert config.api_key == "sk-remote"
    assert config.model_fast == "fast-model"
    assert config.model_capable == "capable-model"
    assert config.max_tokens == 256


def test_resolve_legacy_anthropic_aliases():
    settings = Settings(
        llm_provider="anthropic",
        anthropic_api_key="sk-legacy",
        anthropic_model_haiku="haiku-x",
        anthropic_model_sonnet="sonnet-x",
    )
    config = resolve_llm_runtime_config(settings)
    assert config.api_key == "sk-legacy"
    assert config.model_fast == "haiku-x"
    assert config.model_capable == "sonnet-x"


def test_resolve_legacy_ollama_aliases():
    settings = Settings(
        llm_provider="ollama",
        ollama_url="http://localhost:11434",
        ollama_model_fast="fast-local",
        ollama_model_capable="capable-local",
    )
    config = resolve_llm_runtime_config(settings)
    assert config.base_url == "http://localhost:11434"
    assert config.model_fast == "fast-local"
    assert config.model_capable == "capable-local"
    assert config.api_key == ""


def test_unknown_provider_lists_registered():
    settings = Settings.model_construct(llm_provider="nope")
    with pytest.raises(ValueError, match="registered"):
        resolve_llm_runtime_config(settings)


def test_anthropic_requires_api_key():
    settings = Settings(llm_provider="anthropic", anthropic_api_key="")
    with pytest.raises(ValueError, match="LLM API key"):
        resolve_llm_runtime_config(settings)
