"""Unit tests for Tool RAG (filter → retrieve → shortlist)."""

from __future__ import annotations

from api.app.agent.tool_rag import (
    DEFAULT_TOP_K,
    DefaultToolRag,
    HybridToolRetriever,
    KeywordToolRetriever,
    PolicyToolFilter,
    SkinnyToolRow,
    build_retrieval_query,
    clamp_top_k,
    index_row_from_ref,
    load_full_tool_schema,
    skinny_catalog,
    summarize_workflow_body,
)
from api.app.agent.tools import ToolRef


class _FakeDiscovery:
    def __init__(self, refs: list[ToolRef]) -> None:
        self._refs = refs

    def find(self, name: str, *, client_id: str) -> ToolRef | None:
        _ = client_id
        for ref in self._refs:
            if ref.name == name:
                return ref
        return None

    def list_tools(self, *, client_id: str) -> list[ToolRef]:
        _ = client_id
        return list(self._refs)


def _ref(
    name: str,
    *,
    kind: str = "code",
    description: str | None = None,
    config: dict | None = None,
) -> ToolRef:
    return ToolRef(
        name=name,
        source="registry",
        kind=kind,
        description=description,
        config=config,
    )


def test_clamp_top_k_bounds():
    assert clamp_top_k(1) == 5
    assert clamp_top_k(100) == 20
    assert clamp_top_k(None) == DEFAULT_TOP_K


def test_policy_filter_drops_disabled_and_destructive():
    refs = [
        _ref("post_slack_message", description="Post a message"),
        _ref("delete_file", description="Delete a file"),
        _ref("legacy_tool", config={"enabled": False}),
    ]
    kept = PolicyToolFilter().filter(refs, client_id="t1")
    names = [r.name for r in kept]
    assert names == ["post_slack_message"]


def test_keyword_retriever_shortlists_relevant_tools():
    rows = [
        index_row_from_ref(_ref("create_powerpoint", description="Build a pptx deck")),
        index_row_from_ref(_ref("fetch_channel_history", description="Read Slack history")),
        index_row_from_ref(_ref("send_email", description="Send an email")),
        index_row_from_ref(_ref("parse_spreadsheet", description="Parse excel sheets")),
        index_row_from_ref(_ref("notify_oncall", description="Page on-call")),
        index_row_from_ref(_ref("zip_archive", description="Zip files")),
    ]
    # Force ranking by using more candidates than top_k
    ranked = KeywordToolRetriever().retrieve(
        "create powerpoint from spreadsheet excel",
        rows,
        top_k=5,
    )
    names = [r.name for r in ranked]
    assert "create_powerpoint" in names
    assert "parse_spreadsheet" in names
    assert len(names) == 5


def test_hybrid_falls_back_to_keyword_without_embeddings():
    rows = [
        index_row_from_ref(_ref(f"tool_{i}", description=f"desc {i}"))
        for i in range(8)
    ]
    rows.append(
        index_row_from_ref(_ref("send_email", description="email delivery"))
    )
    ranked = HybridToolRetriever(embeddings=None).retrieve(
        "send email",
        rows,
        top_k=5,
    )
    assert ranked[0].name == "send_email"


def test_default_tool_rag_returns_skinny_rows_only():
    refs = [
        _ref(
            "csvkit",
            kind="cli",
            description="CSV toolkit",
            config={
                "subcommands": {"in2csv": {"purpose": "convert"}},
                "example_queries": ["convert excel to csv"],
            },
        ),
        _ref("send_email", description="Send email"),
    ]
    rag = DefaultToolRag(top_k=12)
    shortlist = rag.shortlist(
        client_id="t1",
        query="convert excel spreadsheet",
        discovery=_FakeDiscovery(refs),
    )
    assert all(isinstance(row, SkinnyToolRow) for row in shortlist)
    catalog = skinny_catalog(shortlist)
    assert catalog
    assert "subcommands" not in catalog[0]
    assert "config" not in catalog[0]


def test_load_full_tool_schema_lazy():
    ref = _ref(
        "csvkit",
        kind="cli",
        description="CSV toolkit",
        config={"subcommands": {"csvstat": {"purpose": "stats"}}},
    )
    full = load_full_tool_schema(ref)
    assert full["subcommands"]["csvstat"]["purpose"] == "stats"


def test_summarize_workflow_body_keeps_relevant_sections():
    body = "\n".join(
        [
            "1. Gather team status from Slack.",
            "2. Compose a weekly digest.",
            "3. Post the digest to #status.",
            "4. Optional: archive old threads.",
            "noise " * 200,
            "5. Email a PDF of the result.",
        ]
    )
    summary = summarize_workflow_body(body, query="email PDF result", max_chars=200)
    assert len(summary) <= 220
    assert "Email a PDF" in summary or "email" in summary.lower()


def test_build_retrieval_query_includes_attachment_hints():
    q = build_retrieval_query(
        "Make a report",
        attachments=[{"filename": "finance.xlsx", "type": "application/vnd.ms-excel"}],
        workflow_title="Weekly status",
    )
    assert "finance.xlsx" in q
    assert "Weekly status" in q
