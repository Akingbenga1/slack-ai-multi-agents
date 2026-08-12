"""LLM provider factory + adapters (Sprint 33.1–33.4)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from api.app.agent.llm import (
    AnthropicChatModel,
    OllamaChatModel,
    OllamaError,
    StubChatModel,
    get_chat_model,
)
from api.app.settings import Settings


def test_factory_stub_provider():
    settings = Settings(llm_provider="stub", anthropic_api_key="")
    model = get_chat_model(settings)
    assert isinstance(model, StubChatModel)
    result = model.complete(
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
        model_tier="fast",
    )
    assert result.model == "stub-fast"
    assert "stub:fast" in result.text


def test_factory_force_stub():
    settings = Settings(llm_provider="anthropic", anthropic_api_key="sk-test")
    assert isinstance(get_chat_model(settings, force_stub=True), StubChatModel)


def test_factory_anthropic_requires_key():
    settings = Settings(llm_provider="anthropic", anthropic_api_key="")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_chat_model(settings)


def test_factory_anthropic_with_key():
    settings = Settings(llm_provider="anthropic", anthropic_api_key="sk-test")
    model = get_chat_model(settings)
    assert isinstance(model, AnthropicChatModel)
    assert model._model_id("fast") == settings.anthropic_model_haiku
    assert model._model_id("capable") == settings.anthropic_model_sonnet


def test_anthropic_complete_maps_tier_and_records_resolved_model():
    """Anthropic path without live API — injected client (mirrors Ollama recorded HTTP)."""
    settings = Settings(
        llm_provider="anthropic",
        anthropic_api_key="sk-test",
        anthropic_model_haiku="claude-haiku-fixture",
        anthropic_max_tokens=128,
    )
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text="hosted reply")],
        usage=SimpleNamespace(input_tokens=7, output_tokens=4),
    )
    model = AnthropicChatModel(settings, client=client)
    result = model.complete(
        system="sys",
        messages=[{"role": "user", "content": "q"}],
        model_tier="fast",
    )
    assert result.text == "hosted reply"
    assert result.model == "claude-haiku-fixture"
    assert result.input_tokens == 7
    assert result.output_tokens == 4
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-fixture"
    assert kwargs["max_tokens"] == 128


def test_factory_ollama():
    settings = Settings(
        llm_provider="ollama",
        ollama_url="http://localhost:11434",
        ollama_model_fast="llama-fast",
        ollama_model_capable="llama-capable",
    )
    model = get_chat_model(settings)
    assert isinstance(model, OllamaChatModel)
    assert model._model_id("fast") == "llama-fast"
    assert model._model_id("capable") == "llama-capable"


def test_ollama_complete_openai_compat():
    """Recorded OpenAI-compatible chat completion (no live Ollama)."""
    settings = Settings(
        llm_provider="ollama",
        ollama_url="http://ollama.test",
        ollama_model_fast="tag-fast",
        ollama_max_tokens=64,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content.decode())
        assert body["model"] == "tag-fast"
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(
            200,
            json={
                "model": "tag-fast",
                "choices": [
                    {"message": {"role": "assistant", "content": "local reply"}}
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://ollama.test") as client:
        model = OllamaChatModel(settings, http_client=client, max_retries=1)
        result = model.complete(
            system="sys",
            messages=[{"role": "user", "content": "q"}],
            model_tier="fast",
        )
    assert result.text == "local reply"
    assert result.model == "tag-fast"
    assert result.input_tokens == 3
    assert result.output_tokens == 2


def test_ollama_http_error():
    settings = Settings(llm_provider="ollama", ollama_url="http://ollama.test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://ollama.test") as client:
        model = OllamaChatModel(settings, http_client=client, max_retries=1)
        with pytest.raises(OllamaError):
            model.complete(
                system="sys",
                messages=[{"role": "user", "content": "q"}],
                model_tier="capable",
            )


def test_factory_unknown_provider():
    settings = Settings.model_construct(llm_provider="nope")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_chat_model(settings)
