"""Provider mapping for the neutral tool-calling transcript."""

from __future__ import annotations

import json

from api.app.agent.llm import (
    ToolCall,
    _to_anthropic_messages,
    _to_openai_messages,
    assistant_action_message,
    tool_observation_message,
)


def _transcript() -> list[dict]:
    call_a = ToolCall(name="run_python", arguments={"script": "print(1)"}, id="c1")
    call_b = ToolCall(name="inspect_workspace", arguments={}, id="c2")
    return [
        {"role": "user", "content": "goal"},
        assistant_action_message("working on it", [call_a, call_b]),
        tool_observation_message(tool_call_id="c1", name="run_python", content="ok"),
        tool_observation_message(
            tool_call_id="c2",
            name="inspect_workspace",
            content="failed",
            is_error=True,
        ),
        {"role": "user", "content": "continue"},
    ]


def test_anthropic_mapping_emits_tool_use_blocks():
    mapped = _to_anthropic_messages(_transcript())
    assistant = mapped[1]
    assert assistant["role"] == "assistant"
    types = [block["type"] for block in assistant["content"]]
    assert types == ["text", "tool_use", "tool_use"]
    assert assistant["content"][1]["id"] == "c1"
    assert assistant["content"][1]["input"] == {"script": "print(1)"}


def test_anthropic_mapping_merges_consecutive_tool_results():
    """The Messages API expects one user turn carrying all tool results."""
    mapped = _to_anthropic_messages(_transcript())
    results_turn = mapped[2]
    assert results_turn["role"] == "user"
    assert [b["type"] for b in results_turn["content"]] == [
        "tool_result",
        "tool_result",
    ]
    assert [b["tool_use_id"] for b in results_turn["content"]] == ["c1", "c2"]
    assert results_turn["content"][1]["is_error"] is True
    # Every requested call is answered exactly once.
    assert len(mapped) == 4


def test_openai_mapping_uses_function_calls_and_tool_role():
    mapped = _to_openai_messages("system text", _transcript())
    assert mapped[0] == {"role": "system", "content": "system text"}
    assistant = mapped[2]
    assert assistant["role"] == "assistant"
    assert [c["function"]["name"] for c in assistant["tool_calls"]] == [
        "run_python",
        "inspect_workspace",
    ]
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {
        "script": "print(1)"
    }
    observations = [m for m in mapped if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in observations] == ["c1", "c2"]


def test_plain_text_transcript_still_maps_unchanged():
    plain = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "carry on"},
    ]
    assert _to_anthropic_messages(plain) == plain
    openai_mapped = _to_openai_messages("sys", plain)
    assert openai_mapped[1:] == plain


def test_anthropic_mapping_never_ends_on_an_assistant_turn():
    """A trailing assistant turn would be read as prefill and rejected."""
    reflected = [
        {"role": "user", "content": "goal"},
        {"role": "assistant", "content": "my approach is not working"},
    ]
    mapped = _to_anthropic_messages(reflected)
    assert [m["role"] for m in mapped] == ["user", "assistant", "user"]
    assert mapped[:2] == reflected
    assert str(mapped[-1]["content"]).strip()


def test_anthropic_mapping_ending_in_tool_results_is_left_alone():
    call = ToolCall(name="run_python", arguments={}, id="c1")
    transcript = [
        {"role": "user", "content": "goal"},
        assistant_action_message("", [call]),
        tool_observation_message(tool_call_id="c1", name="run_python", content="ok"),
    ]
    mapped = _to_anthropic_messages(transcript)
    assert [m["role"] for m in mapped] == ["user", "assistant", "user"]
    assert mapped[-1]["content"][0]["type"] == "tool_result"


def test_openai_mapping_keeps_a_trailing_assistant_turn():
    """Only the Anthropic wire format forbids this, so OpenAI is untouched."""
    reflected = [
        {"role": "user", "content": "goal"},
        {"role": "assistant", "content": "my approach is not working"},
    ]
    mapped = _to_openai_messages("sys", reflected)
    assert mapped[-1] == {"role": "assistant", "content": "my approach is not working"}
