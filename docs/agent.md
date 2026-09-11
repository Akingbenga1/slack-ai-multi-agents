# Agent runtime

Product invoke is **`plan_and_execute`** → Deep Agents harness
(`api/app/agent/harness.py`). Callers pass tenant + question (+ optional
attachments); the harness stages inputs in a tenant workspace, runs the
model with a local shell backend, promotes outputs, and verifies observable
artifacts.

Slack mention/DM and admin/dry-run paths all enter through the same facade.
There is no separate orchestrator/executor role loop on the product path.

## Contract

| Concern | Guarantee |
| ------- | --------- |
| Tenant | Every run requires `client_id`; workspace and promotion stay tenant-scoped |
| Inputs | Attachments are staged into the run workspace (originals not mutated) |
| Work | Model completes the plain-English request using workspace + shell tools |
| Outputs | New artifacts are promoted; outcome verification checks real files/relations |
| Entry | `plan_and_execute` only — no Slack posting inside the harness |

## Live modules

| Module | Role |
| ------ | ---- |
| `facade.py` | Single product entry (`plan_and_execute`) |
| `harness.py` | Deep Agents adapter + workspace promote + verify |
| `workspace.py` | Per-run workspace create / stage / promote |
| `outcome_verifier.py` / `outcome_relations.py` | Independent outcome checks |
| `sandbox.py` | Child-process environment scrubbing for shell/uvx |
| `dry_run_files.py` | Dry-run attachment resolve/store helpers |
| `llm.py` / `llm_config.py` | Chat adapters + role-named LLM settings |
| `guardrails.py` | Tenant required + hedge helpers |
| `tools.py` / `tool_routes.py` | DB tool catalog (admin/ops) |
| `mcp_host*.py` / `cli_host*.py` | Control-plane readiness (not called by harness) |
| `routes.py` | `POST /agent/dry-run`, config / schedules |
| `checkpointer.py` | Optional LangGraph saver factory (legacy continuity; Wave 3) |

## Slack live path

`POST /slack/events` (mention / DM) → Gate → Intake → `plan_and_execute` → Deliver.

| Piece | Module |
| ----- | ------ |
| Event filter + question + thread key | `api/app/slack/echo.py` |
| Public entry + entitlement helpers | `api/app/slack/agent_reply.py` |
| Pipeline stages | `api/app/slack/reply_pipeline.py` |
| Post-agent delivery Strategies | `api/app/slack/delivery/` |
| Answer formatting | `api/app/slack/formatting.py` |

File rename / PDF upload side effects live under `api/app/slack/files/`.
Shared workflow library store/list/copy/edit lives under
`api/app/workflows/` + `api/app/slack/workflow_actions.py` (not the deleted
agent workflow classifier).

## Org agent settings

`GET` / `PATCH /agent/config` — display name, `system_prompt`, channel allowlist.
Schedules: `GET` / `PATCH /agent/schedules`. Portal UI: `/app/agent`.

## LLM provider

Role-named configuration lives in `api/app/agent/llm_config.py`.

| `LLM_PROVIDER` | Adapter shape | Required env |
| -------------- | ------------- | ------------ |
| `stub` | Offline deterministic replies | none (cannot drive live harness without injection) |
| `anthropic` | Native Messages API | `LLM_API_KEY` (or legacy `ANTHROPIC_API_KEY`), model tiers |
| `ollama` | OpenAI-compatible HTTP (local) | `LLM_BASE_URL` or `OLLAMA_URL`, model tiers; key optional |
| `openai_compat` | OpenAI-compatible HTTP (any host) | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_FAST`, `LLM_MODEL_CAPABLE` |

Prefer neutral vars: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_FAST`, `LLM_MODEL_CAPABLE`, `LLM_MAX_TOKENS`.

## Dry-run

**API** (Bearer JWT + tenant context):

```http
POST /agent/dry-run
{"question": "Compress this PDF", "conversation_id": "optional"}
```

**CLI:**

```bash
uv run python scripts/agent_dry_run.py \
  --client-id aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa \
  --question "Turn this PDF into a Word document"
```

Harness runs need a real provider (or an injected `harness_agent` /
`harness_runner` in tests). `LLM_PROVIDER=stub` alone cannot drive Deep Agents.

## Guardrails

Helpers: `api/app/agent/guardrails.py` (`HEDGE_MESSAGE`, `require_tenant_client_id`,
`filter_chunks_for_tenant`). Tenant id is required on every harness run.
