"""Compose / graph / policy vendor isolation (Sprint 33.4)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_AGENT = _REPO / "api" / "app" / "agent"

# Product surface must not name chat vendors (Strategy + Adapter boundary).
_FORBIDDEN = re.compile(
    r"\b(anthropic|claude|openai|ollama|haiku|sonnet)\b",
    re.IGNORECASE,
)

_ISOLATED_MODULES = (
    _AGENT / "nodes" / "compose.py",
    _AGENT / "graph.py",
    _AGENT / "policy.py",
)


def test_compose_graph_policy_have_no_vendor_names():
    for path in _ISOLATED_MODULES:
        text = path.read_text(encoding="utf-8")
        hit = _FORBIDDEN.search(text)
        assert hit is None, f"{path.name} mentions vendor {hit.group(0)!r}"


def test_llm_module_does_not_import_anthropic_at_top_level():
    """Stub / Ollama paths stay light — Anthropic SDK is lazy inside the adapter."""
    source = (_AGENT / "llm.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            assert "anthropic" not in names
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "anthropic"
    assert "import anthropic" in source


def test_compose_uses_chat_model_protocol_only():
    source = (_AGENT / "nodes" / "compose.py").read_text(encoding="utf-8")
    assert "ChatModel" in source
    assert "get_chat_model" in source
    assert "model.complete(" in source or "result = model.complete(" in source
    assert "AnthropicChatModel" not in source
    assert "OllamaChatModel" not in source
