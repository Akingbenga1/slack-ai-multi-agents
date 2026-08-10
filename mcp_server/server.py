"""FastMCP factory — stdio process exposing tenant-scoped tools."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.tools.agenda import draft_meeting_agenda as default_agenda
from mcp_server.tools.draft import draft_meeting_brief as default_draft
from mcp_server.tools.notes import draft_meeting_notes as default_notes
from mcp_server.tools.onboarding import start_onboarding as default_onboarding
from mcp_server.tools.rename import rename_slack_file_tool as default_rename
from mcp_server.tools.report import draft_report as default_report
from mcp_server.tools.search import search_knowledge_tool as default_search
from mcp_server.tools.workflow import advise_workflow as default_advise
from mcp_server.tools.workflow import get_workflow_template_tool as default_get_workflow

ToolFn = Callable[..., dict[str, Any]]

# Back-compat aliases for callers / tests that type injectables.
SearchToolFn = ToolFn
DraftToolFn = ToolFn
ReportToolFn = ToolFn
OnboardingToolFn = ToolFn
RenameToolFn = ToolFn
GetWorkflowToolFn = ToolFn
AdviseWorkflowToolFn = ToolFn


@dataclass(frozen=True)
class _ToolSpec:
    """One public MCP tool: stable name + description + MCP-facing adapter."""

    name: str
    description: str
    fn: Callable[..., dict[str, Any]]


def create_mcp(
    *,
    name: str = "client-slack-agents",
    search_fn: SearchToolFn | None = None,
    draft_fn: DraftToolFn | None = None,
    agenda_fn: DraftToolFn | None = None,
    notes_fn: DraftToolFn | None = None,
    report_fn: ReportToolFn | None = None,
    onboarding_fn: OnboardingToolFn | None = None,
    rename_fn: RenameToolFn | None = None,
    get_workflow_fn: GetWorkflowToolFn | None = None,
    advise_workflow_fn: AdviseWorkflowToolFn | None = None,
) -> FastMCP:
    """
    Build the bundled MCP server.

    Tools always require ``client_id``. Callables may be injected for tests;
    production uses ``api.app.retrieval.search_knowledge`` under the hood.

    Registration is table-driven (``_ToolSpec`` + ``add_tool``). Adding a new
    grounded draft tool is: outline Strategy + one registry row (and a thin
    signature adapter below when args differ).
    """
    search = search_fn or default_search
    draft = draft_fn or default_draft
    agenda = agenda_fn or default_agenda
    notes = notes_fn or default_notes
    report = report_fn or default_report
    onboarding = onboarding_fn or default_onboarding
    rename = rename_fn or default_rename
    get_workflow = get_workflow_fn or default_get_workflow
    advise = advise_workflow_fn or default_advise

    def search_knowledge(
        client_id: str,
        query: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        return search(
            client_id=client_id,
            query=query,
            limit=limit,
            kind=kind,
            channel=channel,
            filename=filename,
        )

    def draft_meeting_brief(
        client_id: str,
        topic: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        return draft(
            client_id=client_id,
            topic=topic,
            limit=limit,
            kind=kind,
            channel=channel,
        )

    def draft_meeting_agenda(
        client_id: str,
        topic: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        return agenda(
            client_id=client_id,
            topic=topic,
            limit=limit,
            kind=kind,
            channel=channel,
        )

    def draft_meeting_notes(
        client_id: str,
        topic: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        return notes(
            client_id=client_id,
            topic=topic,
            limit=limit,
            kind=kind,
            channel=channel,
        )

    def draft_report(
        client_id: str,
        window_label: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
        topic: str | None = None,
    ) -> dict[str, Any]:
        return report(
            client_id=client_id,
            window_label=window_label,
            limit=limit,
            kind=kind,
            channel=channel,
            topic=topic,
        )

    def start_onboarding(client_id: str) -> dict[str, Any]:
        return onboarding(client_id=client_id)

    def rename_slack_file(
        client_id: str,
        new_filename: str,
        stored_relative_path: str | None = None,
        file_id: str | None = None,
        bot_token: str | None = None,
        question: str | None = None,
    ) -> dict[str, Any]:
        return rename(
            client_id=client_id,
            new_filename=new_filename,
            stored_relative_path=stored_relative_path,
            file_id=file_id,
            bot_token=bot_token,
            question=question,
        )

    def get_workflow_template(
        client_id: str,
        template_id: str,
    ) -> dict[str, Any]:
        return get_workflow(client_id=client_id, template_id=template_id)

    def advise_workflow(
        client_id: str,
        question: str,
        template_id: str | None = None,
        body_text: str | None = None,
        title: str | None = None,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        return advise(
            client_id=client_id,
            question=question,
            template_id=template_id,
            body_text=body_text,
            title=title,
            limit=limit,
            kind=kind,
            channel=channel,
        )

    registry: Sequence[_ToolSpec] = (
        _ToolSpec(
            name="search_knowledge",
            description=(
                "Tenant-scoped knowledge search (RAG). ``client_id`` is required "
                "(fail-closed). Optional filters: kind, channel, filename."
            ),
            fn=search_knowledge,
        ),
        _ToolSpec(
            name="draft_meeting_brief",
            description=(
                "Draft a meeting brief outline from tenant knowledge for ``topic``. "
                "``client_id`` is required. Returns structured sections + citations; "
                "does not invent facts beyond retrieved evidence."
            ),
            fn=draft_meeting_brief,
        ),
        _ToolSpec(
            name="draft_meeting_agenda",
            description=(
                "Draft a meeting agenda from tenant knowledge for ``topic``. "
                "``client_id`` is required. Returns numbered items + citations; "
                "does not invent facts beyond retrieved evidence."
            ),
            fn=draft_meeting_agenda,
        ),
        _ToolSpec(
            name="draft_meeting_notes",
            description=(
                "Draft meeting notes from recent tenant context for ``topic``. "
                "``client_id`` is required. Returns sections (decisions, actions, "
                "open questions) + citations; does not invent outcomes beyond evidence."
            ),
            fn=draft_meeting_notes,
        ),
        _ToolSpec(
            name="draft_report",
            description=(
                "Draft a recurring report (themes, decisions, open questions) for "
                "``window_label``. ``client_id`` is required. Returns sections + "
                "citations; does not invent facts beyond retrieved evidence."
            ),
            fn=draft_report,
        ),
        _ToolSpec(
            name="start_onboarding",
            description=(
                "Start client onboarding for this tenant. Currently a stub: returns a "
                "clear “not configured” message. ``client_id`` is required. Does not "
                "invent checklist steps."
            ),
            fn=start_onboarding,
        ),
        _ToolSpec(
            name="rename_slack_file",
            description=(
                "Rename a tenant-stored org copy of a Slack attachment (primary). "
                "Optionally update Slack file title via files.edit when ``file_id`` "
                "and ``bot_token`` are provided. Slack has no full filename rename "
                "API. ``client_id`` is required (fail-closed)."
            ),
            fn=rename_slack_file,
        ),
        _ToolSpec(
            name="get_workflow_template",
            description=(
                "Fetch a shared/personal workflow template for this tenant. "
                "``client_id`` is required (fail-closed). Cross-tenant ids are not found."
            ),
            fn=get_workflow_template,
        ),
        _ToolSpec(
            name="advise_workflow",
            description=(
                "Advise how to operationalise a workflow from file text or a stored "
                "template id, plus optional tenant RAG. ``client_id`` is required. "
                "Does not invent process steps beyond the file / knowledge evidence."
            ),
            fn=advise_workflow,
        ),
    )

    mcp = FastMCP(name)
    for spec in registry:
        mcp.add_tool(spec.fn, name=spec.name, description=spec.description)
    return mcp


def main() -> None:
    """Entry: run over stdio (default). Ctrl+C / EOF stops the process."""
    create_mcp().run(transport="stdio")


if __name__ == "__main__":
    main()
