# Bundled MCP server (Sprint 15)

Separate **stdio** process next to the API. Tools enforce a required `client_id`
(fail-closed) and reuse `api.app.retrieval.search_knowledge`.

## Start / stop

```bash
# From repo root (loads .env via Settings when tools hit Qdrant/TEI)
uv run python -m mcp_server
```

- **Transport:** stdio (default). The process speaks MCP JSON-RPC on stdin/stdout.
- **Stop:** Ctrl+C, or close the client pipe (EOF). Do not send logs to stdout — only MCP frames.

Optional Inspector smoke (separate terminal):

```bash
npx -y @modelcontextprotocol/inspector uv run python -m mcp_server
```

## Tools

| Tool | Required args | Purpose |
| ---- | ------------- | ------- |
| `search_knowledge` | `client_id`, `query` | Tenant-scoped RAG top-k (+ optional `kind` / `channel` / `filename`) |
| `draft_meeting_brief` | `client_id`, `topic` | Deterministic meeting-brief outline from retrieved evidence |
| `draft_meeting_agenda` | `client_id`, `topic` | Deterministic numbered agenda from retrieved evidence |
| `draft_meeting_notes` | `client_id`, `topic` | Deterministic notes (decisions / actions / open Qs) from recent context |
| `draft_report` | `client_id`, `window_label` | Recurring digest (themes / decisions / open Qs) over a window |
| `start_onboarding` | `client_id` | Onboarding **process** stub — always “not configured” (not tenant signup; see `docs/onboarding.md`) |
| `rename_slack_file` | `client_id`, `new_filename` | Rename tenant org copy (+ optional Slack title); see `docs/slack-file-actions.md` |
| `get_workflow_template` | `client_id`, `template_id` | Fetch tenant-scoped workflow library row (Sprint 24) |
| `advise_workflow` | `client_id`, `question` | File/template-grounded operationalisation outline (+ optional RAG) |

Missing / blank `client_id` → tool error (`TenantFilterRequired`).

## Package layout

| Path | Role |
| ---- | ---- |
| `mcp_server/server.py` | `create_mcp()` (table-driven `add_tool`) + `main()` stdio entry |
| `mcp_server/__main__.py` | `python -m mcp_server` |
| `mcp_server/tools/grounded.py` | `run_grounded_draft` Template Method + `hit_as_citation` (Sprint 27) |
| `mcp_server/tools/search.py` | `search_knowledge` wrapper |
| `mcp_server/tools/draft.py` | `draft_meeting_brief` outline Strategy |
| `mcp_server/tools/agenda.py` | `draft_meeting_agenda` outline Strategy |
| `mcp_server/tools/notes.py` | `draft_meeting_notes` outline Strategy |
| `mcp_server/tools/report.py` | `draft_report` outline Strategy |
| `mcp_server/tools/onboarding.py` | `start_onboarding` stub |
| `mcp_server/tools/rename.py` | `rename_slack_file` (Sprint 23) |
| `mcp_server/tools/workflow.py` | `get_workflow_template` + `advise_workflow` (Sprint 24) |
| `mcp_server/serialize.py` | Citation → JSON dict |

See also `docs/onboarding.md` (extension point for a future checklist state machine).

## Tests (no Compose)

```bash
uv run pytest tests/mcp -q
```

Uses in-memory MCP transport + stub search (no Qdrant/TEI).

## LangGraph (Task 15.4 / 16.2–16.4 / 17.1 / 18.1)

Agent graph: **route → tools → compose**. The **tools** node uses `invoke_mcp` in `api/app/agent/mcp_client.py` (Adapter) — not N duplicated `*_via_mcp` transports. Typed helpers remain for call-site clarity.

- Default Q&A / coordination: MCP `search_knowledge`
- `meeting_brief` workflow: MCP `draft_meeting_brief` (outline + citations; compose may polish)
- `meeting_agenda` workflow: MCP `draft_meeting_agenda` (numbered items + citations; compose may polish)
- `meeting_notes` workflow: MCP `draft_meeting_notes` (prefers Slack hits, widens to docs; compose may polish)
- `report` workflow / `run_report` subgraph: MCP `draft_report` (themes / decisions / open Qs over `window_label`)
- `onboarding` workflow: MCP `start_onboarding` (deterministic “not configured” stub; no RAG)

```bash
# Default: MCP tools via in-process FastMCP (API/worker)
# AGENT_RETRIEVE_BACKEND=mcp
# AGENT_MCP_TRANSPORT=in_process

# Opt-in: spawn stdio MCP per tool call (external / debugging)
# AGENT_MCP_TRANSPORT=stdio

# Escape hatch (tests / debugging): skip MCP, in-process retrieval only
# AGENT_RETRIEVE_BACKEND=direct

# Optional stdio launch override
# AGENT_MCP_COMMAND=C:\path\to\python.exe
# AGENT_MCP_ARGS=-m mcp_server
```

Unit tests inject `mcp_call_tool` or `search_fn` so they do not spawn a real subprocess.
