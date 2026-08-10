"""Anthropic chat wrapper with offline stub (Sprint 13)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import anthropic

from api.app.agent.state import ModelTier
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
    """Deterministic compose for tests / laptop without ANTHROPIC_API_KEY."""

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
        # Pull a short evidence snippet if present in the last user turn
        evidence_note = ""
        if "Evidence:" in user:
            tail = user.split("Evidence:", 1)[1].strip()
            first_line = tail.splitlines()[0] if tail else ""
            evidence_note = f" Based on: {first_line[:160]}"
        text = (
            f"[stub:{model_tier}] Grounded reply (offline).{evidence_note}"
        ).strip()
        # Rough token estimate for budget accounting in stub mode
        est = max(1, (len(system) + len(user) + len(text)) // 4)
        return LlmResult(
            text=text,
            model=f"stub-{model_tier}",
            input_tokens=est // 2,
            output_tokens=est - est // 2,
        )


class AnthropicChatModel:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        max_retries: int = 3,
    ) -> None:
        self.settings = settings or get_settings()
        key = (self.settings.anthropic_api_key or "").strip()
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is empty")
        self._client = anthropic.Anthropic(api_key=key, max_retries=max_retries)

    def _model_id(self, tier: ModelTier) -> str:
        if tier == "sonnet":
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


def get_chat_model(
    settings: Settings | None = None,
    *,
    force_stub: bool = False,
) -> ChatModel:
    settings = settings or get_settings()
    if force_stub or not (settings.anthropic_api_key or "").strip():
        logger.info("agent_llm_mode=stub")
        return StubChatModel()
    logger.info("agent_llm_mode=anthropic")
    return AnthropicChatModel(settings)


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
