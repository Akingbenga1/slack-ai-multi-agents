"""Chat model Strategy + LLM provider Factory (Sprint 13 / 33 / 43).

Compose and the graph know only ``ChatModel.complete`` and generic tiers
(``fast`` / ``capable``). Vendor SDKs and model ids live in adapters;
``get_chat_model`` selects by ``LLM_PROVIDER``. Optional tool schemas may be
passed in; adapters return text or structured ``ToolCall`` values and never
execute those tools.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

import httpx

from api.app.agent.state import ModelTier
from api.app.http_retry import call_with_retries, is_transient_http_status
from api.app.logging_config import get_logger, log_agent_prompts
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.llm")


def _log_complete_prompts(
    *,
    system: str,
    messages: list[dict[str, str]],
    model_tier: ModelTier,
) -> None:
    """Write system + user prompts to ``app.log`` for the active agent role."""
    try:
        from api.app.agent.base import current_agent_role
    except Exception:
        return
    role = current_agent_role.get()
    if not role:
        return
    log_agent_prompts(
        role=role,
        system=system,
        messages=list(messages or []),
        model_tier=str(model_tier),
    )

@dataclass(frozen=True)
class ToolSchema:
    """Optional tool description passed into ``ChatModel.complete``."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    """One model-requested tool invocation. Adapters never execute this."""

    name: str
    arguments: dict[str, Any]
    id: str


@dataclass(frozen=True)
class LlmResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    tool_calls: tuple[ToolCall, ...] = ()

    @property
    def total_tokens(self) -> int:
        return max(0, self.input_tokens) + max(0, self.output_tokens)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class ChatModel(Protocol):
    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model_tier: ModelTier,
        tools: list[ToolSchema] | None = None,
        max_tokens: int | None = None,
    ) -> LlmResult: ...


class StubChatModel:
    """Deterministic compose for tests / ``LLM_PROVIDER=stub``.

    Never invents tool calls unless the caller injects ``scripted_tool_calls``.
    ``scripted_text`` (optional JSON plan) is returned as ``text`` when no
    scripted tool calls apply. Performs no I/O.
    """

    def __init__(
        self,
        *,
        scripted_tool_calls: Sequence[ToolCall] | None = None,
        scripted_text: str | dict[str, Any] | list[Any] | None = None,
    ) -> None:
        self._scripted_tool_calls = tuple(scripted_tool_calls or ())
        if isinstance(scripted_text, (dict, list)):
            self._scripted_text: str | None = json.dumps(scripted_text)
        else:
            self._scripted_text = scripted_text

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model_tier: ModelTier,
        tools: list[ToolSchema] | None = None,
        max_tokens: int | None = None,
    ) -> LlmResult:
        _log_complete_prompts(
            system=system, messages=messages, model_tier=model_tier
        )
        _ = max_tokens
        _ = system
        user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user = m.get("content") or ""
                break
        evidence_note = ""
        if "Evidence:" in user:
            tail = user.split("Evidence:", 1)[1].strip()
            first_line = tail.splitlines()[0] if tail else ""
            evidence_note = f" Based on: {first_line[:160]}"
        bound = _bound_tools(tools)
        if bound and self._scripted_tool_calls:
            est = max(1, (len(system) + len(user)) // 4)
            return LlmResult(
                text="",
                model=f"stub-{model_tier}",
                input_tokens=est // 2,
                output_tokens=max(1, est - est // 2),
                tool_calls=self._scripted_tool_calls,
            )
        if self._scripted_text is not None:
            text = self._scripted_text
        else:
            text = (
                f"[stub:{model_tier}] Grounded reply (offline).{evidence_note}"
            ).strip()
        est = max(1, (len(system) + len(user) + len(text)) // 4)
        return LlmResult(
            text=text,
            model=f"stub-{model_tier}",
            input_tokens=est // 2,
            output_tokens=est - est // 2,
        )


class AnthropicChatModel:
    """Anthropic Messages API adapter — maps ``fast``/``capable`` → vendor model ids."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        max_retries: int = 3,
        client: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if client is not None:
            self._client = client
            return
        key = (self.settings.anthropic_api_key or "").strip()
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY is empty; set the key or use LLM_PROVIDER=stub"
            )
        # Lazy import so stub/Ollama paths do not need the Anthropic SDK loaded.
        import anthropic

        self._client = anthropic.Anthropic(api_key=key, max_retries=max_retries)

    def _model_id(self, tier: ModelTier) -> str:
        if tier == "capable":
            return self.settings.anthropic_model_sonnet
        return self.settings.anthropic_model_haiku

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model_tier: ModelTier,
        tools: list[ToolSchema] | None = None,
        max_tokens: int | None = None,
    ) -> LlmResult:
        _log_complete_prompts(
            system=system, messages=messages, model_tier=model_tier
        )
        model = self._model_id(model_tier)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": (
                max_tokens
                if max_tokens is not None
                else self.settings.anthropic_max_tokens
            ),
            "system": system,
            "messages": [
                {"role": m["role"], "content": m["content"]} for m in messages
            ],
        }
        mapped = _to_anthropic_tools(_bound_tools(tools))
        if mapped:
            kwargs["tools"] = mapped
        resp = self._client.messages.create(**kwargs)
        text, calls = _from_anthropic_content(getattr(resp, "content", None))
        usage = getattr(resp, "usage", None)
        in_tok = int(getattr(usage, "input_tokens", 0) or 0)
        out_tok = int(getattr(usage, "output_tokens", 0) or 0)
        return LlmResult(
            text=text,
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            tool_calls=calls,
        )


class OllamaChatModel:
    """Ollama / OpenAI-compatible chat completions adapter (HTTP)."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        max_retries: int = 3,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        base = (self.settings.ollama_url or "").strip().rstrip("/")
        if not base:
            raise ValueError("OLLAMA_URL is empty")
        self.base_url = base
        self.max_retries = max_retries
        self._http_client = http_client

    def _model_id(self, tier: ModelTier) -> str:
        if tier == "capable":
            return self.settings.ollama_model_capable
        return self.settings.ollama_model_fast

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model_tier: ModelTier,
        tools: list[ToolSchema] | None = None,
        max_tokens: int | None = None,
    ) -> LlmResult:
        _log_complete_prompts(
            system=system, messages=messages, model_tier=model_tier
        )
        model = self._model_id(model_tier)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                *[
                    {"role": m["role"], "content": m["content"]}
                    for m in messages
                    if m.get("role") in ("user", "assistant", "system")
                ],
            ],
            "max_tokens": int(
                max_tokens
                if max_tokens is not None
                else self.settings.ollama_max_tokens
            ),
            "stream": False,
        }
        mapped = _to_openai_tools(_bound_tools(tools))
        if mapped:
            payload["tools"] = mapped
        url = f"{self.base_url}/v1/chat/completions"

        def _once() -> dict[str, Any]:
            if self._http_client is not None:
                r = self._http_client.post(url, json=payload)
            else:
                with httpx.Client(timeout=120.0) as client:
                    r = client.post(url, json=payload)
            if is_transient_http_status(r.status_code):
                raise OllamaError(
                    f"Ollama chat HTTP {r.status_code}: {r.text[:300]}"
                )
            if r.status_code >= 400:
                raise OllamaError(
                    f"Ollama chat HTTP {r.status_code}: {r.text[:300]}"
                )
            data = r.json()
            if not isinstance(data, dict):
                raise OllamaError(f"unexpected Ollama response type: {type(data)!r}")
            return data

        data = call_with_retries(
            _once,
            max_retries=self.max_retries,
            should_retry=_ollama_should_retry,
            label="ollama.chat",
        )
        text = _openai_compat_text(data)
        calls = _openai_compat_tool_calls(data)
        if not text and not calls:
            text = "(empty model response)"
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
        resolved = str(data.get("model") or model)
        return LlmResult(
            text=text,
            model=resolved,
            input_tokens=in_tok,
            output_tokens=out_tok,
            tool_calls=calls,
        )


class OllamaError(RuntimeError):
    """Ollama / OpenAI-compatible chat request failed."""


def _ollama_should_retry(exc: BaseException) -> bool:
    if isinstance(exc, OllamaError):
        return "HTTP 429" in str(exc) or "HTTP 5" in str(exc)
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


def _bound_tools(tools: list[ToolSchema] | None) -> list[ToolSchema]:
    if not tools:
        return []
    return [t for t in tools if (t.name or "").strip()]


def _json_object_schema(parameters: dict[str, Any] | None) -> dict[str, Any]:
    if parameters:
        return parameters
    return {"type": "object", "properties": {}}


def _to_anthropic_tools(tools: list[ToolSchema]) -> list[dict[str, Any]]:
    return [
        {
            "name": t.name,
            "description": t.description or "",
            "input_schema": _json_object_schema(t.parameters),
        }
        for t in tools
    ]


def _to_openai_tools(tools: list[ToolSchema]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": _json_object_schema(t.parameters),
            },
        }
        for t in tools
    ]


def _block_as_dict(block: Any) -> dict[str, Any]:
    if isinstance(block, dict):
        return block
    return {
        "type": getattr(block, "type", None),
        "text": getattr(block, "text", None),
        "id": getattr(block, "id", None),
        "name": getattr(block, "name", None),
        "input": getattr(block, "input", None),
    }


def _from_anthropic_content(content: Any) -> tuple[str, tuple[ToolCall, ...]]:
    parts: list[str] = []
    calls: list[ToolCall] = []
    blocks = content if isinstance(content, list) else []
    for block in blocks:
        data = _block_as_dict(block)
        btype = data.get("type")
        name = data.get("name")
        call_id = data.get("id")
        raw_input = data.get("input")
        is_tool = btype == "tool_use" or (
            name and call_id and raw_input is not None and not data.get("text")
        )
        if is_tool:
            args = raw_input if isinstance(raw_input, dict) else {}
            calls.append(
                ToolCall(
                    name=str(name or ""),
                    arguments=args,
                    id=str(call_id or ""),
                )
            )
            continue
        text = data.get("text")
        if text:
            parts.append(str(text))
    joined = "\n".join(parts).strip()
    if not joined and not calls:
        joined = "(empty model response)"
    return joined, tuple(calls)


def _parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _openai_compat_tool_calls(data: dict[str, Any]) -> tuple[ToolCall, ...]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ()
    first = choices[0]
    if not isinstance(first, dict):
        return ()
    message = first.get("message")
    if not isinstance(message, dict):
        return ()
    raw = message.get("tool_calls")
    if not isinstance(raw, list):
        return ()
    calls: list[ToolCall] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fn = item.get("function") if isinstance(item.get("function"), dict) else {}
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        calls.append(
            ToolCall(
                name=name,
                arguments=_parse_tool_arguments(fn.get("arguments")),
                id=str(item.get("id") or ""),
            )
        )
    return tuple(calls)


def _openai_compat_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
    text = first.get("text")
    if isinstance(text, str):
        return text.strip()
    return ""


def get_chat_model(
    settings: Settings | None = None,
    *,
    force_stub: bool = False,
) -> ChatModel:
    """Factory: select chat adapter by ``LLM_PROVIDER`` (or force stub)."""
    settings = settings or get_settings()
    if force_stub:
        logger.info("agent_llm_mode=stub reason=force_stub")
        return StubChatModel()

    provider = (settings.llm_provider or "anthropic").strip().lower()
    if provider == "stub":
        logger.info("agent_llm_mode=stub")
        return StubChatModel()
    if provider == "ollama":
        logger.info("agent_llm_mode=ollama base=%s", settings.ollama_url)
        return OllamaChatModel(settings)
    if provider == "anthropic":
        logger.info("agent_llm_mode=anthropic")
        return AnthropicChatModel(settings)

    raise ValueError(
        f"Unknown LLM_PROVIDER={provider!r}; expected anthropic|ollama|stub"
    )


def message_content(msg: Any) -> str:
    """Extract text from LangChain / dict message objects."""
    if isinstance(msg, dict):
        content = msg.get("content", "")
    else:
        content = getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        bits: list[str] = []
        for part in content:
            if isinstance(part, str):
                bits.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                bits.append(str(part.get("text") or ""))
            else:
                text = getattr(part, "text", None)
                if text:
                    bits.append(str(text))
        return "\n".join(bits)
    return str(content or "")
