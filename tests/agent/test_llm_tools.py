"""ChatModel tool calling (Sprint 43). Adapters must not execute tools."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

from api.app.agent.llm import (
    AnthropicChatModel,
    OllamaChatModel,
    StubChatModel,
    ToolCall,
    ToolSchema,
)
from api.app.settings import Settings

_SEARCH = ToolSchema(
    name="search_knowledge",
    description="Search tenant knowledge",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)

_SCRIPTED = ToolCall(
    name="search_knowledge",
    arguments={"query": "budget"},
    id="call_scripted",
)


def test_stub_no_tools_returns_text_zero_tool_calls():
    model = StubChatModel()
    result = model.complete(
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
        model_tier="fast",
    )
    assert "stub:fast" in result.text
    assert result.tool_calls == ()
    assert not result.has_tool_calls
    assert result.total_tokens > 0


def test_stub_empty_tools_stays_text_only_even_if_scripted():
    model = StubChatModel(scripted_tool_calls=[_SCRIPTED])
    result = model.complete(
        system="sys",
        messages=[{"role": "user", "content": "hi"}],
        model_tier="fast",
        tools=[],
    )
    assert result.tool_calls == ()
    assert "stub:fast" in result.text


def test_stub_scripted_tool_call_is_structured_not_slack_post():
    model = StubChatModel(scripted_tool_calls=[_SCRIPTED])
    result = model.complete(
        system="sys",
        messages=[{"role": "user", "content": "find the budget"}],
        model_tier="capable",
        tools=[_SEARCH],
    )
    assert result.has_tool_calls
    assert result.tool_calls == (_SCRIPTED,)
    assert result.tool_calls[0].name == "search_knowledge"
    assert result.tool_calls[0].arguments == {"query": "budget"}
    assert result.tool_calls[0].id == "call_scripted"
    assert result.text == ""
    assert "chat.postMessage" not in result.text
    assert "slack" not in result.text.lower()
    assert result.total_tokens > 0


def test_stub_does_not_invent_tool_calls_when_tools_bound():
    model = StubChatModel()
    result = model.complete(
        system="sys",
        messages=[{"role": "user", "content": "use a tool"}],
        model_tier="fast",
        tools=[_SEARCH],
    )
    assert result.tool_calls == ()
    assert "stub:fast" in result.text


def test_stub_performs_no_io(monkeypatch):
    boom = MagicMock(side_effect=AssertionError("stub must not I/O"))
    monkeypatch.setattr("httpx.Client", boom)
    monkeypatch.setattr("api.app.agent.mcp_client.call_mcp_tool", boom, raising=False)
    model = StubChatModel(scripted_tool_calls=[_SCRIPTED])
    model.complete(
        system="s",
        messages=[{"role": "user", "content": "q"}],
        model_tier="fast",
        tools=[_SEARCH],
    )
    boom.assert_not_called()


def test_anthropic_maps_tools_and_parses_tool_use_without_executing(monkeypatch):
    boom = MagicMock(side_effect=AssertionError("adapter must not execute tools"))
    monkeypatch.setattr("api.app.agent.mcp_client.call_mcp_tool", boom, raising=False)
    settings = Settings(
        llm_provider="anthropic",
        anthropic_api_key="sk-test",
        anthropic_model_haiku="claude-haiku-fixture",
        anthropic_max_tokens=128,
    )
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                id="toolu_1",
                name="search_knowledge",
                input={"query": "q1"},
            )
        ],
        usage=SimpleNamespace(input_tokens=11, output_tokens=5),
    )
    model = AnthropicChatModel(settings, client=client)
    result = model.complete(
        system="sys",
        messages=[{"role": "user", "content": "q"}],
        model_tier="fast",
        tools=[_SEARCH],
    )
    assert result.tool_calls == (
        ToolCall(name="search_knowledge", arguments={"query": "q1"}, id="toolu_1"),
    )
    assert result.text == ""
    assert result.input_tokens == 11
    assert result.output_tokens == 5
    assert result.total_tokens == 16
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["tools"] == [
        {
            "name": "search_knowledge",
            "description": "Search tenant knowledge",
            "input_schema": _SEARCH.parameters,
        }
    ]
    client.messages.create.assert_called_once()
    boom.assert_not_called()


def test_anthropic_maps_required_tool_choice_and_stop_reason():
    settings = Settings(
        llm_provider="anthropic",
        anthropic_api_key="sk-test",
        anthropic_model_haiku="claude-haiku-fixture",
    )
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[],
        usage=SimpleNamespace(input_tokens=4, output_tokens=2),
        stop_reason="end_turn",
    )
    model = AnthropicChatModel(settings, client=client)
    result = model.complete(
        system="sys",
        messages=[{"role": "user", "content": "q"}],
        model_tier="fast",
        tools=[_SEARCH],
        tool_choice="required",
    )
    assert result.is_empty
    assert result.stop_reason == "end_turn"
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "any"}


def test_openai_compat_maps_required_tool_choice_and_stop_reason():
    settings = Settings(
        llm_provider="ollama",
        ollama_url="http://ollama.test",
        ollama_model_fast="tag-fast",
        ollama_max_tokens=64,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["tool_choice"] == "required"
        return httpx.Response(
            200,
            json={
                "model": "tag-fast",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": ""},
                    }
                ],
                "usage": {"prompt_tokens": 2, "completion_tokens": 0},
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://ollama.test") as client:
        model = OllamaChatModel(settings, http_client=client, max_retries=1)
        result = model.complete(
            system="sys",
            messages=[{"role": "user", "content": "q"}],
            model_tier="fast",
            tools=[_SEARCH],
            tool_choice="required",
        )
    assert result.is_empty
    assert result.stop_reason == "stop"


def test_anthropic_omit_tools_does_not_send_vendor_tools():
    settings = Settings(
        llm_provider="anthropic",
        anthropic_api_key="sk-test",
        anthropic_model_haiku="claude-haiku-fixture",
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
    assert result.tool_calls == ()
    assert "tools" not in client.messages.create.call_args.kwargs


def test_ollama_maps_openai_tools_and_parses_without_executing(monkeypatch):
    boom = MagicMock(side_effect=AssertionError("adapter must not execute tools"))
    monkeypatch.setattr("api.app.agent.mcp_client.call_mcp_tool", boom, raising=False)
    settings = Settings(
        llm_provider="ollama",
        ollama_url="http://ollama.test",
        ollama_model_fast="tag-fast",
        ollama_max_tokens=64,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["tools"] == [
            {
                "type": "function",
                "function": {
                    "name": "search_knowledge",
                    "description": "Search tenant knowledge",
                    "parameters": _SEARCH.parameters,
                },
            }
        ]
        return httpx.Response(
            200,
            json={
                "model": "tag-fast",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_oa_1",
                                    "type": "function",
                                    "function": {
                                        "name": "search_knowledge",
                                        "arguments": '{"query": "q1"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 9, "completion_tokens": 3},
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, base_url="http://ollama.test") as client:
        model = OllamaChatModel(settings, http_client=client, max_retries=1)
        result = model.complete(
            system="sys",
            messages=[{"role": "user", "content": "q"}],
            model_tier="fast",
            tools=[_SEARCH],
        )
    assert result.tool_calls == (
        ToolCall(name="search_knowledge", arguments={"query": "q1"}, id="call_oa_1"),
    )
    assert result.text == ""
    assert result.input_tokens == 9
    assert result.output_tokens == 3
    boom.assert_not_called()
