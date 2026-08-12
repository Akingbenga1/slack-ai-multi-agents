# Agent runtime (Sprint 13–14 / 39)

Product invoke is **`run_agent` / `run_report`** via an **`AgentRuntime`** adapter. LangGraph (`StateGraph` + checkpointer) is the first implementation (`LangGraphAgentRuntime`). Graph shape: **route → tools → compose**. The tools node invokes bundled MCP `search_knowledge` over stdio (Sprint 15). Slack mention/DM path posts grounded replies (Sprint 14).

No `AGENT_RUNTIME` env this sprint (single runtime). `AGENT_CHECKPOINTER=memory|postgres` stays the small LangGraph saver factory — not a separate vendor Strategy.

## State

| Field | Purpose |
| ----- | ------- |
| `client_id` | Tenant id (required on every node; never dropped) |
| `messages` | Chat history (`add_messages`) |
| `retrieved_chunks` | Serialized `search_knowledge` hits (tenant-filtered) |
| `workflow` | `qa` \| `summarize` \| `status` \| `meeting_brief` \| `meeting_agenda` \| `meeting_notes` \| `report` \| `onboarding` \| `file_analyse` \| `file_pdf_export` \| `file_rename` \| `workflow_store` \| `workflow_list` \| `workflow_copy` \| `workflow_edit` \| `unknown` |
| `model_tier` | `fast` (default) \| `capable` |
| `complexity_flags` | Escalation reasons |
| `answer` / `hedge` / `usage_tokens` | Compose outputs |
| `org_system_prompt` | Optional overlay from `agent_configs.system_prompt` (Sprint 19) |
| `attached_evidence` | Slack attachment payloads (Sprint 23) — primary evidence for file workflows |

## Nodes

1. **route** — classify workflow (`qa` / `status` / `summarize` / meeting `brief`·`agenda`·`notes` / `report` / `onboarding`); set Haiku/Sonnet via complexity heuristics  
2. **tools** — MCP client → `search_knowledge` (tenant `client_id` required; fail-closed). Meeting drafts / `draft_report` / `start_onboarding` for typed workflows. Set `AGENT_RETRIEVE_BACKEND=direct` only for in-process debugging.  
3. **compose** — selected `ChatModel` (or stub) grounded on evidence with **workflow-specific prompts**; records `llm_tokens` usage. Onboarding returns the stub message without an LLM call. Org `system_prompt` (if set) is prepended to the workflow system prompt.

## Workflow registry & Strategies (Sprint 25–26 / 30)

Pattern intent and phased rollout: [`Project-Documents/review.md`](../Project-Documents/review.md) (§5 registry / delivery; P0–P6). Apply patterns only for real smells — see [`Project-Documents/TechStack/software-developement-patterns.md`](../Project-Documents/TechStack/software-developement-patterns.md) (+ `references/behavioral.md` for Strategy).

| Concern | Location |
| ------- | -------- |
| Package entry / exports | `api/app/agent/workflows/` |
| Metadata registry (`WorkflowMeta`, prompts, escalate, `delivery_hint`) | `api/app/agent/workflows/registry.py` |
| Ordered classifier rules (Chain-of-rules / Strategy) | `api/app/agent/workflows/rules.py` |
| Tools-node Strategy map | `api/app/agent/workflows/tool_strategies.py` |
| Intent helpers (PDF / rename / advise cues) | `api/app/agent/workflows/intents.py` |
| Slack post-agent DeliveryStrategy map | `api/app/slack/delivery/` (`strategies.py`) |

### How to add a workflow Strategy

1. Add the name to `WorkflowName` in `api/app/agent/state.py`.
2. Register `WorkflowMeta` in `registry.py` (description, `prompt_key`, escalate, `delivery_hint`).
3. Add an ordered classifier rule in `rules.py` (do **not** extend a monolithic regex ladder in `route`).
4. Register a `ToolStrategy` in `tool_strategies.py` (or reuse RAG / meeting / report strategies) and a compose prompt in `prompts.py`.
5. If Slack side effects differ (PDF upload, rename, library confirm), register a DeliveryStrategy under `api/app/slack/delivery/` and point `delivery_hint` at it.

New capability = new registration. Keep the runtime shell (`route → tools → compose`) and Slack pipeline stages stable. Swapping the agent framework later touches `AgentRuntime` / `langgraph_adapter`, not Slack/billing/workflow modules.

### Slack delivery Strategies

After the agent run, `reply_pipeline` resolves a DeliveryStrategy via `resolve_delivery_strategy` / workflow `delivery_hint`:

| Strategy | Typical workflows | Effect |
| -------- | ----------------- | ------ |
| `DefaultPostStrategy` | `qa`, summarize, status, meetings, report, … | `chat.postMessage` (+ Sources) |
| `PdfUploadStrategy` | `file_pdf_export` | Upload PDF to channel / thread |
| `RenameDeliveryStrategy` | `file_rename` | Slack file title update |
| `LibraryConfirmStrategy` | `workflow_store` / list / copy / edit | Deterministic confirmations |
| `AdviseDeliveryStrategy` | `workflow_advise` | Advice reply (file-grounded) |

Map: `DELIVERY_STRATEGIES` in `api/app/slack/delivery/strategies.py`. File helpers live under `api/app/slack/files/` (not inside the delivery Strategies).

## Org agent settings (Sprint 19.1)

`GET` / `PATCH /agent/config` — display name (`extra.display_name`), `system_prompt`, channel `allowlist`. Schedules: `GET` / `PATCH /agent/schedules` (unified Strategy-validated write; legacy `/jobs/.../schedule` adapters remain). Kind Strategies live in `api/app/schedules/kinds.py` (`SCHEDULE_KIND_STRATEGIES`); persistence in `api/app/schedules/store.py`. Portal UI: `/app/agent` — see `docs/portal.md` / `docs/celery.md`.

Scheduled digests use a **report subgraph** (`tools → compose`, no route) via `run_report` — see below.

## Coordination-style prompts (Sprint 14.4)

Status / who-said-what / thread summaries use the same RAG path with distinct compose prompts (`api/app/agent/prompts.py`):

| Workflow | Trigger examples | Compose behaviour |
| -------- | ---------------- | ----------------- |
| `status` | “status on…”, “who said…”, “any update…” | Attribution-first bullets; speakers from Evidence `user=` |
| `summarize` | “summarize…”, “catch me up…”, “tl;dr” | Structured thread/channel summary; speakers when known |
| `qa` | everything else | Standard grounded Q&A |

Evidence blocks include Slack `user` / `channel` / `ts` metadata so attribution is possible. Status, summarize, and meeting workflows escalate to Sonnet (complexity policy).

## Meeting workflows (Sprint 16)

Meeting asks classify in `route` before generic Q&A.

| Workflow | Trigger examples | Tools / compose |
| -------- | ---------------- | --------------- |
| `meeting_brief` | “brief me for…”, “meeting brief…”, “prep me for…”, “pre-meeting…” | MCP `draft_meeting_brief` → citations + outline; compose polishes on Sonnet |
| `meeting_agenda` | “agenda for…”, “draft an agenda…” | MCP `draft_meeting_agenda` → numbered items; compose polishes on Sonnet |
| `meeting_notes` | “meeting notes…”, “notes from the call…” | MCP `draft_meeting_notes` → decisions/actions/open Qs from recent context; compose polishes on Sonnet |

Bare “brief overview…” stays `qa` (avoids false positives). Meeting workflows set `workflow:*` flags → Sonnet. State may carry `meeting_draft` (markdown outline) into compose.

## Slack file workflows (Sprint 23)

Attachment-grounded analysis / PDF export / rename intents:

| Workflow | Trigger examples | Behaviour |
| -------- | ---------------- | --------- |
| `file_analyse` | “analyse this attached report…”, “based on this file…” | Attachment text → evidence (+ optional RAG); Sonnet |
| `file_pdf_export` | “produce a PDF of competitor analysis…” | Same compose, then **fpdf2** PDF + `files.upload`; if ask also says rename, org-copy rename follows |
| `file_rename` | “rename the file to …” | Org-copy rename + best-effort Slack title (`files.edit`); MCP `rename_slack_file` |

`attached_evidence` on state bypasses the hard RAG hedge when the file parsed. Heavy workflows also check `jobs_daily` before the graph. See `docs/slack-file-actions.md`.

## Shared workflow library (Sprint 24)

Channel upload → org shared library + copy/edit (`docs/workflow-library.md`):

| Workflow | Trigger examples | Behaviour |
| -------- | ---------------- | --------- |
| `workflow_store` | “store this workflow in the shared library…” | Attachment intake → `workflow_templates`; idempotent by hash / Slack file id |
| `workflow_list` | “list shared workflows…” | Tenant-scoped list (+ optional personal drafts) |
| `workflow_copy` | “copy workflow \<uuid\>…” | Personal draft; original unchanged |
| `workflow_edit` | “update my draft title to…” | Owner-only personal draft edit |
| `workflow_advise` | “advise how we can make this workflow work…” | Attachment or stored template → compose (Sonnet); optional RAG secondary |

Store / list / copy / edit short-circuit after intake with deterministic Slack confirmations (no full RAG compose). Advice runs the agent compose path with file evidence (no generic hedge when the file is present). Portal: `/app/workflows` · API: `/workflows` · MCP: `get_workflow_template`, `advise_workflow`.

## Recurring reports (Sprint 17.1)

Scheduled digests (TM-13) use a dedicated **report subgraph** and prompt:

| Piece | Detail |
| ----- | ------ |
| Workflow | `report` — themes / decisions / open questions over a window |
| MCP | `draft_report` (`window_label`, optional `channel` / `topic`) |
| Subgraph | `build_report_graph` / `run_report` — **tools → compose** (no route) |
| Compose | `SYSTEM_REPORT`; Sonnet via `workflow:report` |
| State | `report_window`, optional `report_channel`; draft outline in `meeting_draft` |

Interactive asks (“weekly report”, “team digest”, “generate a report”) also classify to `report` on the main graph (before bare “digest” → `summarize`).

```bash
# Programmatic digest (Celery will call this in 17.3)
AGENT_CHECKPOINTER=memory uv run python -c "
from api.app.agent import run_report
from langgraph.checkpoint.memory import MemorySaver
from api.app.agent.llm import StubChatModel
from api.app.settings import Settings
print(run_report(
    client_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    window_label='last 7 days',
    settings=Settings(agent_checkpointer='memory', anthropic_api_key=''),
    checkpointer=MemorySaver(),
    chat_model=StubChatModel(),
    record_usage=False,
)['workflow'])
"
```

Tenant schedule fields + Beat posting land in Tasks 17.2–17.3.

Configure per tenant via `GET`/`PATCH /agent/schedules` (`slack_history_sync` + `recurring_report` blocks) — legacy `GET`/`PATCH /jobs/recurring-report/schedule` still works. See `docs/celery.md` / `docs/portal.md`.

Force or schedule a post: `POST /jobs/recurring-report` or Beat (`worker.dispatch_recurring_reports` → `worker.recurring_report`). Path: prefer channel sync → `run_report` → direct `chat.postMessage`. Failures mark `jobs` (`kind=recurring_report`) and record a `job` usage event; successes record `report_post`.

## Onboarding stub (Sprint 18.1)

Honest deferred process — no invented checklist:

| Piece | Detail |
| ----- | ------ |
| Workflow | `onboarding` — explicit start/process phrasing only |
| MCP | `start_onboarding` (`client_id`) → `configured=false` + clear message |
| Compose | Deterministic stub text (no LLM, not the RAG hedge) |
| Knowledge Q&A | “onboarding checklist for new hires” stays `qa` → `search_knowledge` |

Triggers: “start onboarding”, “begin client onboarding”, “onboarding process/workflow”, `start_onboarding`. Extension point for a future state machine: `docs/onboarding.md`. This stub is **not** org registration (`/signup` / Sprint 31).

## Slack live path (Sprint 14)

`POST /slack/events` (mention / DM) → install-store token → Gate → Intake → RunAgent → Deliver (`chat.postMessage` / PDF / rename / library confirm).

| Piece | Module |
| ----- | ------ |
| Event filter + question + thread key | `api/app/slack/echo.py` |
| Public entry + entitlement helpers | `api/app/slack/agent_reply.py` |
| Pipeline stages (Gate → Deliver) | `api/app/slack/reply_pipeline.py` |
| Post-agent DeliveryStrategy map | `api/app/slack/delivery/` |
| Answer + Sources formatting | `api/app/slack/formatting.py` |

- Mentions reply **in-thread** (`thread_ts` = existing thread or mention `ts`).
- DMs reply top-level; checkpointer `conversation_id` = DM channel id.
- Mentions: `conversation_id` = `{channel}:{thread_root}`.
- Ack Slack immediately; agent runs in a FastAPI `BackgroundTask`.
- Active plan + `agent` entitlement + token headroom required; otherwise a clear denial is posted (no LangGraph).
- Grounded answers append a short `*Sources:*` list (omitted when hedged).
- Coordination asks (status / who-said-what / summarize) use dedicated prompts; still RAG-grounded.
- Structured replies (Sprint 16.5): before posting, common Markdown (`#` headings, `**bold**`, `-` bullets) is normalised to Slack mrkdwn so meeting briefs / agendas / notes stay scannable.

Live verify still needs Slack app + tunnel + **active** plan for the tenant (Stripe Checkout or local `apply_plan_state` / webhook). See `docs/slack-app-setup.md`.

## Guardrails (13.4)

- **Hard hedge:** if retrieval returns no tenant-scoped chunks **above** `AGENT_MIN_SCORE` (default `0.70`), compose returns a fixed hedge message and **does not call** the LLM (no invented facts; `usage_tokens=0`).
- **Tenant filter:** every node requires `client_id`; tools/compose re-filter chunks so foreign-tenant hits never reach the answer.
- Helpers: `api/app/agent/guardrails.py` (`HEDGE_MESSAGE`, `require_tenant_client_id`, `filter_chunks_for_tenant`).

## Model policy (13.3 / 33)

- Graph tiers: **`fast`** (default) and **`capable`** (escalation)
- Complexity flags (`compare`, `analyze`, long questions, summarize/status/meeting/report/…) escalate to **capable**
- Each LLM adapter maps tiers to vendor model ids (Anthropic: Haiku / Sonnet; Ollama: `OLLAMA_MODEL_FAST` / `OLLAMA_MODEL_CAPABLE`)
- Token usage → `usage_events` (`event_type=llm_tokens`) with the **resolved** model id from the adapter

## LLM provider (Sprint 33)

| `LLM_PROVIDER` | Backend |
| -------------- | ------- |
| `anthropic` (demo default) | Anthropic Messages API (`ANTHROPIC_API_KEY`, Haiku/Sonnet model envs) |
| `ollama` | OpenAI-compatible `POST {OLLAMA_URL}/v1/chat/completions` |
| `stub` | Deterministic offline reply for tests / laptop dry-runs |

Offline is **`LLM_PROVIDER=stub`**. An empty `ANTHROPIC_API_KEY` no longer selects the stub by itself.

Compose, the graph, and model-tier policy know only `ChatModel` + `fast` / `capable`. Vendor SDKs and model ids live in adapters (`api/app/agent/llm.py`); the Anthropic SDK is imported lazily inside that adapter.

## Checkpointer (13.2)

- Default **Postgres** (`AGENT_CHECKPOINTER=postgres`) via `langgraph-checkpoint-postgres`
- Thread key: `{client_id}:{conversation_id}` (tenant-scoped continuity)
- Tables created on first `setup()` (not Alembic)
- `AGENT_CHECKPOINTER=memory` for unit tests / no-DB smoke

## Dry-run

**API** (Bearer JWT + tenant context):

```http
POST /agent/dry-run
{"question": "What is the refund policy?", "conversation_id": "optional"}
```

**CLI:**

```bash
uv run python scripts/agent_dry_run.py \
  --client-id aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa \
  --question "onboarding checklist for new hires"
```

Without `LLM_PROVIDER=stub` (or injecting `StubChatModel`), compose calls the selected provider. Retrieval still needs Qdrant + TEI (or inject fixtures via smoke corpus). When evidence is missing, the response is the hard hedge message regardless of stub/Anthropic/Ollama.

### Live smoke (Sprint 13 exit)

```bash
# Ensure sample corpus is searchable, then dry-run
uv run python scripts/search_knowledge_smoke.py
AGENT_CHECKPOINTER=memory uv run python scripts/agent_dry_run.py \
  --client-id aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa \
  --question "refund policy within 30 days" \
  --memory --no-usage
```

Expect `hedge=False`, at least one retrieved chunk, and a grounded stub answer citing evidence.

## Modules

- `api/app/agent/runtime.py` — `AgentRuntime` Protocol + `default_agent_runtime()`
- `api/app/agent/langgraph_adapter.py` — LangGraph `StateGraph` + invoke (first adapter)
- `api/app/agent/state.py`, `graph.py` (re-export), `run.py` (product facade), `checkpointer.py`, `policy.py`, `llm.py`, `guardrails.py`, `prompts.py`
- `api/app/agent/workflows/` — registry, classifier rules, tool Strategies (see **Workflow registry & Strategies** above)
- `api/app/agent/nodes/{route,retrieve,compose,tools}.py`
- `api/app/agent/routes.py` — `POST /agent/dry-run`, config / schedules
- `api/app/slack/agent_reply.py` — Slack mention/DM orchestration entry
- `api/app/slack/reply_pipeline.py` / `delivery/` — stages + swappable delivery Strategies
- Pattern plan: `Project-Documents/review.md` · guidance: `Project-Documents/TechStack/software-developement-patterns.md`
