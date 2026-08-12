"""Chat model Strategy + LLM provider Factory (Sprint 13 / 33).

Compose and the graph know only ``ChatModel.complete`` and generic tiers
(``fast`` / ``capable``). Vendor SDKs and model ids live in adapters;
``get_chat_model`` selects by ``LLM_PROVIDER``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from api.app.agent.state import ModelTier
from api.app.http_retry import call_with_retries, is_transient_http_status
from api.app.logging_config import get_logger
from api.app.settings import Settings, get_settings

logger = get_logger("api.agent.llm")


@dataclass(frozen=True)
class LlmResult:
    text: str
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return max(0, self.input_tokens) + max(0, self.output_tokens)


class ChatModel(Protocol):
    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model_tier: ModelTier,
    ) -> LlmResult: ...


class StubChatModel:
    """Deterministic compose for tests / ``LLM_PROVIDER=stub``."""

    def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model_tier: ModelTier,
    ) -> LlmResult:
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
    ) -> LlmResult:
        model = self._model_id(model_tier)
        resp = self._client.messages.create(
            model=model,
            max_tokens=self.settings.anthropic_max_tokens,
            system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
        )
        parts: list[str] = []
        for block in resp.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        usage = getattr(resp, "usage", None)
        in_tok = int(getattr(usage, "input_tokens", 0) or 0)
        out_tok = int(getattr(usage, "output_tokens", 0) or 0)
        return LlmResult(
            text="\n".join(parts).strip() or "(empty model response)",
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
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
    ) -> LlmResult:
        model = self._model_id(model_tier)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                *[
                    {"role": m["role"], "content": m["content"]}
                    for m in messages
                    if m.get("role") in ("user", "assistant", "system")
                ],
            ],
            "max_tokens": int(self.settings.ollama_max_tokens),
            "stream": False,
        }
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
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        in_tok = int(usage.get("prompt_tokens") or 0)
        out_tok = int(usage.get("completion_tokens") or 0)
        resolved = str(data.get("model") or model)
        return LlmResult(
            text=text or "(empty model response)",
            model=resolved,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )


class OllamaError(RuntimeError):
    """Ollama / OpenAI-compatible chat request failed."""


def _ollama_should_retry(exc: BaseException) -> bool:
    if isinstance(exc, OllamaError):
        return "HTTP 429" in str(exc) or "HTTP 5" in str(exc)
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


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
