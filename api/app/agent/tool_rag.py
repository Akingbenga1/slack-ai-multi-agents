"""Tool RAG — filter → retrieve → shortlist for planner context.

Abstractions first: callers depend on ``ToolRag`` / ``ToolFilter`` /
``ToolRetriever``. Concrete keyword + hybrid search and policy filtering
sit behind those protocols. The planner receives skinny rows only
(name, kind, short description); full CLI schemas stay out until lookup.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence, runtime_checkable

from api.app.agent.guardrails import find_destructive_plan_violations
from api.app.agent.tools import ToolDiscovery, ToolRef
from api.app.logging_config import get_logger, log_tool_rag_activity

logger = get_logger("api.agent.tool_rag")

DEFAULT_TOP_K = 12
MIN_TOP_K = 5
MAX_TOP_K = 20
DEFAULT_WORKFLOW_BODY_CHARS = 1500

_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.I)
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ToolIndexRow:
    """Indexable tool metadata used for retrieval (not the planner prompt)."""

    name: str
    kind: str | None = None
    description: str | None = None
    example_queries: tuple[str, ...] = ()
    search_text: str = ""
    source: str = "registry"


@dataclass(frozen=True)
class SkinnyToolRow:
    """Planner-facing catalog row — name, kind, one short description."""

    name: str
    kind: str | None = None
    description: str | None = None

    def as_catalog_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {"name": self.name}
        if self.kind:
            row["kind"] = self.kind
        desc = (self.description or "").strip()
        if desc:
            row["description"] = desc
        return row


@runtime_checkable
class ToolFilter(Protocol):
    """Keep tenant-allowed, enabled, policy-safe tools only."""

    def filter(
        self,
        refs: Sequence[ToolRef],
        *,
        client_id: str,
    ) -> list[ToolRef]:
        ...


@runtime_checkable
class ToolRetriever(Protocol):
    """Rank filtered index rows for a retrieval query."""

    def retrieve(
        self,
        query: str,
        candidates: Sequence[ToolIndexRow],
        *,
        top_k: int,
    ) -> list[ToolIndexRow]:
        ...


@runtime_checkable
class ToolRag(Protocol):
    """End-to-end Tool RAG: filter → retrieve → skinny shortlist."""

    def shortlist(
        self,
        *,
        client_id: str,
        query: str,
        discovery: ToolDiscovery,
        top_k: int | None = None,
    ) -> list[SkinnyToolRow]:
        ...


def clamp_top_k(value: int | None, *, default: int = DEFAULT_TOP_K) -> int:
    raw = default if value is None else int(value)
    return max(MIN_TOP_K, min(MAX_TOP_K, raw))


def build_retrieval_query(
    question: str,
    *,
    attachments: Sequence[dict[str, Any]] | None = None,
    workflow_title: str | None = None,
) -> str:
    """Turn the user request (+ light context) into a retrieval query."""
    parts = [(question or "").strip()]
    for item in attachments or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("filename") or "").strip()
        kind = str(item.get("type") or item.get("mimetype") or "").strip()
        if name:
            parts.append(name)
        if kind:
            parts.append(kind)
    title = (workflow_title or "").strip()
    if title:
        parts.append(title)
    return _WS_RE.sub(" ", " ".join(p for p in parts if p)).strip()


def index_row_from_ref(ref: ToolRef) -> ToolIndexRow:
    """Build an index row from a discovery ref (no full schema dump)."""
    config = ref.config if isinstance(ref.config, dict) else {}
    examples_raw = config.get("example_queries") or config.get("examples") or []
    examples: list[str] = []
    if isinstance(examples_raw, (list, tuple)):
        examples = [str(x).strip() for x in examples_raw if str(x).strip()]
    elif isinstance(examples_raw, str) and examples_raw.strip():
        examples = [examples_raw.strip()]
    description = (ref.description or "").strip() or None
    search_bits = [ref.name, description or "", *examples]
    if ref.kind:
        search_bits.append(ref.kind)
    return ToolIndexRow(
        name=ref.name,
        kind=ref.kind,
        description=description,
        example_queries=tuple(examples),
        search_text=_WS_RE.sub(" ", " ".join(search_bits)).strip().lower(),
        source=ref.source,
    )


def skinny_from_index(row: ToolIndexRow) -> SkinnyToolRow:
    return SkinnyToolRow(
        name=row.name,
        kind=row.kind,
        description=row.description,
    )


def skinny_catalog(rows: Sequence[SkinnyToolRow]) -> list[dict[str, Any]]:
    return [row.as_catalog_dict() for row in rows]


def load_full_tool_schema(ref: ToolRef) -> dict[str, Any]:
    """Lazy-load full config / subcommands after a tool is chosen."""
    payload: dict[str, Any] = {"name": ref.name}
    if ref.kind:
        payload["kind"] = ref.kind
    if ref.description:
        payload["description"] = ref.description
    config = ref.config if isinstance(ref.config, dict) else None
    has_subcommands = False
    if config:
        payload["config"] = config
        subcommands = config.get("subcommands")
        if isinstance(subcommands, dict) and subcommands:
            payload["subcommands"] = subcommands
            has_subcommands = True
    if ref.mcp_server_id is not None:
        payload["mcp_server_id"] = str(ref.mcp_server_id)
    log_tool_rag_activity(
        phase="lazy_load",
        tool_name=ref.name,
        kind=ref.kind,
        source=ref.source,
        has_subcommands=has_subcommands,
        has_config=bool(config),
    )
    return payload


def summarize_workflow_body(
    body: str,
    *,
    query: str = "",
    max_chars: int = DEFAULT_WORKFLOW_BODY_CHARS,
    client_id: str | None = None,
) -> str:
    """Keep short bodies intact; for long ones keep query-relevant slices."""
    text = (body or "").strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    tokens = _tokens(query)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        summary = text[:max_chars]
        log_tool_rag_activity(
            phase="workflow_summarize",
            client_id=client_id,
            original_chars=len(text),
            summary_chars=len(summary),
            max_chars=max_chars,
        )
        return summary

    scored: list[tuple[float, int, str]] = []
    for index, line in enumerate(lines):
        lower = line.lower()
        score = 0.0
        for tok in tokens:
            if tok in lower:
                score += 1.0
        if re.match(r"^(\d+[.)]|[-*•]|step\b)", lower):
            score += 0.25
        scored.append((score, index, line))

    scored.sort(key=lambda item: (-item[0], item[1]))
    chosen: list[tuple[int, str]] = []
    used = 0
    for score, index, line in scored:
        if score <= 0 and chosen:
            continue
        piece = line if used == 0 else f"\n{line}"
        if used + len(piece) > max_chars and chosen:
            break
        chosen.append((index, line))
        used += len(piece)

    if not chosen:
        summary = text[:max_chars].rstrip() + "…"
    else:
        chosen.sort(key=lambda item: item[0])
        summary = "\n".join(line for _, line in chosen)
        if len(summary) > max_chars:
            summary = summary[:max_chars].rstrip() + "…"
        elif len(text) > len(summary):
            summary = summary.rstrip() + "\n…"

    log_tool_rag_activity(
        phase="workflow_summarize",
        client_id=client_id,
        original_chars=len(text),
        summary_chars=len(summary),
        max_chars=max_chars,
        lines_kept=len(chosen),
    )
    return summary


def _tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def _keyword_score(query: str, row: ToolIndexRow) -> float:
    q_tokens = _tokens(query)
    if not q_tokens:
        return 0.0
    hay = row.search_text or f"{row.name} {row.description or ''}".lower()
    name_l = row.name.lower()
    score = 0.0
    for tok in q_tokens:
        if tok == name_l or tok in name_l.replace("_", " ").split():
            score += 3.0
        elif tok in name_l:
            score += 2.0
        elif tok in hay:
            score += 1.0
    # Light length normalization so long descriptions do not dominate.
    return score / math.sqrt(max(1, len(q_tokens)))


class PolicyToolFilter:
    """Drop disabled and policy-unsafe tools; keep tenant discovery output."""

    def filter(
        self,
        refs: Sequence[ToolRef],
        *,
        client_id: str,
    ) -> list[ToolRef]:
        _ = client_id
        out: list[ToolRef] = []
        for ref in refs:
            config = ref.config if isinstance(ref.config, dict) else {}
            if config.get("enabled") is False:
                continue
            if config.get("disabled") is True:
                continue
            probe = [{"tool_name": ref.name, "arguments": {}}]
            if find_destructive_plan_violations(probe):
                continue
            out.append(ref)
        return out


class KeywordToolRetriever:
    """Rank tools by name / description / example-query keyword overlap."""

    def retrieve(
        self,
        query: str,
        candidates: Sequence[ToolIndexRow],
        *,
        top_k: int,
    ) -> list[ToolIndexRow]:
        if not candidates:
            return []
        limit = max(1, int(top_k))
        if len(candidates) <= limit:
            return list(candidates)

        ranked = sorted(
            candidates,
            key=lambda row: (-_keyword_score(query, row), row.name),
        )
        return ranked[:limit]


class HybridToolRetriever:
    """Embeddings + keyword hybrid; falls back to keyword-only on embed errors."""

    def __init__(
        self,
        *,
        embeddings: Any | None = None,
        keyword_weight: float = 0.45,
        semantic_weight: float = 0.55,
    ) -> None:
        self._embeddings = embeddings
        self._keyword_weight = keyword_weight
        self._semantic_weight = semantic_weight
        self._keyword = KeywordToolRetriever()

    def retrieve(
        self,
        query: str,
        candidates: Sequence[ToolIndexRow],
        *,
        top_k: int,
    ) -> list[ToolIndexRow]:
        if not candidates:
            return []
        limit = max(1, int(top_k))
        if len(candidates) <= limit:
            return list(candidates)

        kw_scores = {row.name: _keyword_score(query, row) for row in candidates}
        sem_scores = self._semantic_scores(query, candidates)
        if sem_scores is None:
            return self._keyword.retrieve(query, candidates, top_k=limit)

        ranked = sorted(
            candidates,
            key=lambda row: (
                -(
                    self._keyword_weight * kw_scores.get(row.name, 0.0)
                    + self._semantic_weight * sem_scores.get(row.name, 0.0)
                ),
                row.name,
            ),
        )
        return ranked[:limit]

    def _semantic_scores(
        self,
        query: str,
        candidates: Sequence[ToolIndexRow],
    ) -> dict[str, float] | None:
        if self._embeddings is None:
            return None
        texts = [query.strip()] + [
            (row.search_text or row.name).strip() or row.name for row in candidates
        ]
        if not texts[0]:
            return {row.name: 0.0 for row in candidates}
        try:
            vectors = self._embeddings.embed(texts)
        except Exception:
            logger.info("tool_rag_embed_fallback reason=embed_failed")
            log_tool_rag_activity(
                phase="retrieve_fallback",
                reason="embed_failed",
                mode="keyword",
                candidate_count=len(candidates),
            )
            return None
        if not vectors or len(vectors) != len(texts):
            return None
        qvec = vectors[0]
        scores: dict[str, float] = {}
        for row, vec in zip(candidates, vectors[1:]):
            scores[row.name] = _cosine(qvec, vec)
        return scores


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += float(x) * float(y)
        na += float(x) * float(x)
        nb += float(y) * float(y)
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)


@dataclass
class DefaultToolRag:
    """Concrete Tool RAG pipeline used by the orchestrator."""

    tool_filter: ToolFilter = field(default_factory=PolicyToolFilter)
    retriever: ToolRetriever = field(default_factory=KeywordToolRetriever)
    top_k: int = DEFAULT_TOP_K

    def shortlist(
        self,
        *,
        client_id: str,
        query: str,
        discovery: ToolDiscovery,
        top_k: int | None = None,
    ) -> list[SkinnyToolRow]:
        limit = clamp_top_k(top_k if top_k is not None else self.top_k)
        refs = discovery.list_tools(client_id=client_id)
        filtered = self.tool_filter.filter(refs, client_id=client_id)
        dropped = max(0, len(refs) - len(filtered))
        log_tool_rag_activity(
            phase="filter",
            client_id=client_id,
            query=query,
            discovered_count=len(refs),
            filtered_count=len(filtered),
            dropped_count=dropped,
            filtered_names=[ref.name for ref in filtered],
        )

        indexed = [index_row_from_ref(ref) for ref in filtered]
        retriever_name = type(self.retriever).__name__
        retrieved = self.retriever.retrieve(query, indexed, top_k=limit)
        log_tool_rag_activity(
            phase="retrieve",
            client_id=client_id,
            query=query,
            retriever=retriever_name,
            top_k=limit,
            candidate_count=len(indexed),
            retrieved_count=len(retrieved),
            retrieved_names=[row.name for row in retrieved],
        )

        shortlisted = [skinny_from_index(row) for row in retrieved]
        log_tool_rag_activity(
            phase="shortlist",
            client_id=client_id,
            query=query,
            top_k=limit,
            shortlist_count=len(shortlisted),
            shortlist=[row.as_catalog_dict() for row in shortlisted],
            skinny=True,
            includes_subcommands=False,
        )
        return shortlisted


def get_tool_rag(extra: dict[str, Any] | None = None) -> ToolRag:
    """Resolve Tool RAG from context overrides or settings-backed defaults.

    Embeddings are used only when injected via ``extra["embeddings"]`` so
    offline / stub runs stay on keyword retrieval without calling TEI.
    """
    extra = extra or {}
    injected = extra.get("tool_rag")
    if injected is not None:
        return injected

    settings = extra.get("settings")
    top_k = DEFAULT_TOP_K
    use_embeddings = True
    if settings is not None:
        top_k = int(getattr(settings, "tool_rag_top_k", DEFAULT_TOP_K) or DEFAULT_TOP_K)
        use_embeddings = bool(getattr(settings, "tool_rag_use_embeddings", True))

    embeddings = extra.get("embeddings") if use_embeddings else None
    retriever: ToolRetriever
    if use_embeddings:
        retriever = HybridToolRetriever(embeddings=embeddings)
    else:
        retriever = KeywordToolRetriever()

    return DefaultToolRag(retriever=retriever, top_k=clamp_top_k(top_k))
