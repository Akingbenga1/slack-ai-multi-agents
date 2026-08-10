"""FastMCP factory — stdio process exposing tenant-scoped tools."""

from __future__ import annotations

from collections.abc import Callable
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

SearchToolFn = Callable[..., dict[str, Any]]
DraftToolFn = Callable[..., dict[str, Any]]
ReportToolFn = Callable[..., dict[str, Any]]
OnboardingToolFn = Callable[..., dict[str, Any]]
RenameToolFn = Callable[..., dict[str, Any]]
GetWorkflowToolFn = Callable[..., dict[str, Any]]
AdviseWorkflowToolFn = Callable[..., dict[str, Any]]


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
    mcp = FastMCP(name)

    @mcp.tool()
    def search_knowledge(
        client_id: str,
        query: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Tenant-scoped knowledge search (RAG). ``client_id`` is required
        (fail-closed). Optional filters: kind, channel, filename.
        """
        return search(
            client_id=client_id,
            query=query,
            limit=limit,
            kind=kind,
            channel=channel,
            filename=filename,
        )

    @mcp.tool()
    def draft_meeting_brief(
        client_id: str,
        topic: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """
        Draft a meeting brief outline from tenant knowledge for ``topic``.
        ``client_id`` is required. Returns structured sections + citations;
        does not invent facts beyond retrieved evidence.
        """
        return draft(
            client_id=client_id,
            topic=topic,
            limit=limit,
            kind=kind,
            channel=channel,
        )

    @mcp.tool()
    def draft_meeting_agenda(
        client_id: str,
        topic: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """
        Draft a meeting agenda from tenant knowledge for ``topic``.
        ``client_id`` is required. Returns numbered items + citations;
        does not invent facts beyond retrieved evidence.
        """
        return agenda(
            client_id=client_id,
            topic=topic,
            limit=limit,
            kind=kind,
            channel=channel,
        )

    @mcp.tool()
    def draft_meeting_notes(
        client_id: str,
        topic: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """
        Draft meeting notes from recent tenant context for ``topic``.
        ``client_id`` is required. Returns sections (decisions, actions,
        open questions) + citations; does not invent outcomes beyond evidence.
        """
        return notes(
            client_id=client_id,
            topic=topic,
            limit=limit,
            kind=kind,
            channel=channel,
        )

    @mcp.tool()
    def draft_report(
        client_id: str,
        window_label: str,
        limit: int = 8,
        kind: str | None = None,
        channel: str | None = None,
        topic: str | None = None,
    ) -> dict[str, Any]:
        """
        Draft a recurring report (themes, decisions, open questions) for
        ``window_label``. ``client_id`` is required. Returns sections +
        citations; does not invent facts beyond retrieved evidence.
        """
        return report(
            client_id=client_id,
            window_label=window_label,
            limit=limit,
            kind=kind,
            channel=channel,
            topic=topic,
        )

    @mcp.tool()
    def start_onboarding(client_id: str) -> dict[str, Any]:
        """
        Start client onboarding for this tenant. Currently a stub: returns a
        clear “not configured” message. ``client_id`` is required. Does not
        invent checklist steps.
        """
        return onboarding(client_id=client_id)

    @mcp.tool()
    def rename_slack_file(
        client_id: str,
        new_filename: str,
        stored_relative_path: str | None = None,
        file_id: str | None = None,
        bot_token: str | None = None,
        question: str | None = None,
    ) -> dict[str, Any]:
        """
        Rename a tenant-stored org copy of a Slack attachment (primary).
        Optionally update Slack file title via files.edit when ``file_id``
        and ``bot_token`` are provided. Slack has no full filename rename
        API. ``client_id`` is required (fail-closed).
        """
        return rename(
            client_id=client_id,
            new_filename=new_filename,
            stored_relative_path=stored_relative_path,
            file_id=file_id,
            bot_token=bot_token,
            question=question,
        )

    @mcp.tool()
    def get_workflow_template(
        client_id: str,
        template_id: str,
    ) -> dict[str, Any]:
        """
        Fetch a shared/personal workflow template for this tenant.
        ``client_id`` is required (fail-closed). Cross-tenant ids are not found.
        """
        return get_workflow(client_id=client_id, template_id=template_id)

    @mcp.tool()
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
        """
        Advise how to operationalise a workflow from file text or a stored
        template id, plus optional tenant RAG. ``client_id`` is required.
        Does not invent process steps beyond the file / knowledge evidence.
        """
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

    return mcp


def main() -> None:
    """Entry: run over stdio (default). Ctrl+C / EOF stops the process."""
    create_mcp().run(transport="stdio")


if __name__ == "__main__":
    main()
