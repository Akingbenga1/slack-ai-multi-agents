"""EmbeddingProvider factory smoke (Sprint 35.2)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from api.app.embedding import TeiEmbeddingProvider, get_embedding_provider
from api.app.settings import Settings


def test_factory_defaults_to_tei():
    provider = get_embedding_provider(Settings(embedding_provider="tei"))
    assert isinstance(provider, TeiEmbeddingProvider)
    assert provider.name == "tei"
    assert provider.dim == 384
    assert "bge" in provider.model_id.lower() or provider.model_id


def test_factory_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown EMBEDDING_PROVIDER"):
        get_embedding_provider(Settings(embedding_provider="cohere"))


def test_factory_ollama_not_implemented():
    with pytest.raises(ValueError, match="Ollama"):
        get_embedding_provider(Settings(embedding_provider="ollama"))


def test_factory_openai_not_implemented():
    with pytest.raises(ValueError, match="OpenAI"):
        get_embedding_provider(Settings(embedding_provider="openai"))


def test_tei_adapter_embed_delegates():
    settings = Settings(embedding_dim=3, embedding_model_id="test-model")
    tei = MagicMock()
    tei.model_id = "test-model"
    tei.embed.return_value = [[0.1, 0.2, 0.3]]
    provider = TeiEmbeddingProvider(settings, client=tei)
    assert provider.dim == 3
    assert provider.model_id == "test-model"
    out = provider.embed(["hello"])
    assert out == [[0.1, 0.2, 0.3]]
    tei.embed.assert_called_once_with(["hello"], truncate=True)
