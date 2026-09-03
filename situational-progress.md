# Situational Progress — CodeAct Executor Findings & Hardening Roadmap

_Date: 2026-09-02 · Scope: agent dry-run harness (`/agent/dry-run` → orchestrator → executor ReAct loop) · Status: investigation only, **no code changed** in this pass beyond one planner-prompt edit noted below._

---

## 1. What we ran and what happened

Three plain-English requests were driven through the live `POST /agent/dry-run` endpoint (multipart file attachment, `include_trace=true`), then **independently verified** against the actual produced artifacts rather than trusting the endpoint's self-reported status.

| # | Request | Endpoint status | Verified outcome | Verdict |
|---|---------|-----------------|------------------|---------|
| 1 | Compress `Reference Request Form.pdf` to **< 100 kB** | `succeeded` | 183 kB → **137.2 kB**, text layer intact (3 pages, 3,947 chars) | **Target missed** — smaller, but not under 100 kB |
| 2 | `sample_users.xlsx` → JSON, one object per row | `succeeded` | 5 objects, keys match headers exactly, values match cell-for-cell | **Correct** — contract fully met |
| 3 | `user-workflow.md` outline → PowerPoint (one slide per heading) | `succeeded` (1st run) | Planner **halted**, no `.pptx` produced | **Not fulfilled** |

**Key cross-cutting observation:** the endpoint's `status: succeeded` is **not proof** of outcome. In 2 of 3 cases the reported success overstated the real result (PDF over target; PPTX not produced at all). Durable behaviour must verify observable outcomes against the contract, not logs/return codes/model self-report.

---

## 2. Root causes found (evidence-backed)

### 2.1 Planner falsely refused an entire output format (PPTX)

- **Cause:** the orchestrator planning system prompt contained an instance-specific ban — `"...generate PDF or PPTX..."` — meant to describe the planner's *role boundary* ("you only plan"), but the model read it literally as *forbidden output types* and emitted a `halt`: "This planner cannot generate PowerPoint (PPTX) files."
- **Why PDF slipped through but PPTX didn't:** the PDF task was phrased as *compressing an existing* file (a transformation), never matching "generate PDF"; the PPTX task literally says "Turn this into a PowerPoint," matching "generate … PPTX."
- **Status:** we applied a **generalised, role-framed** prompt change (removed the format list; stated the Executor produces all artifact types of any file type via `execute_goal`). After the change the planner correctly plans a single `execute_goal` step (`workflow: document_conversion`). This was the only code/prompt edit in this pass.
- **Lesson (abstract-outcome rule):** never encode instance-specific format/tool/error names into shared prompts or core modules; describe **roles and outcomes**, so new formats plug in without touching the centre.

### 2.2 Executor stalled and produced no file (deeper, still-open defect)

After the planner fix, the re-run **failed in the executor** with `status: failed`, answer `"identical action already attempted"`, loop telemetry `executed=3 recorded=9 produced=0 stop="no progress: actions kept repeating"`.

The persisted step transcript (`agent_plan_steps.result.attempts`) shows the exact sequence:

```
#0 inspect_workspace           ok=True
#1 run_python  ok=False  error_class=invalid_action  msg="script is required"
#2 run_python  ok=False  error_class=invalid_action  msg="script is required"
#3 run_python  ok=False  refused=True  "identical action already attempted"
#4..#8 run_python  refused=True  (x6 total)  → stop: "actions kept repeating"
```

**Two compounding defects:**

- **(A) Token starvation truncates the tool call.** The executor's ReAct model calls run at **`max_tokens = 1024`** (`llm_max_tokens=1024` → `config.max_tokens`) on `claude-sonnet-5` **with extended thinking**. A longer script (parse Markdown headings + build slides via `python-pptx`) exceeds the budget; thinking consumes the allotment and the `run_python` tool call arrives with an **empty/missing `script`**. This is the first task whose script exceeds the ceiling — which is why the shorter XLSX and PDF scripts succeeded.
  - **Corroborated by a prior in-repo probe** (terminal `528440`): at `max_tokens` 1024/4096 the model returned `stop_reason=max_tokens` with **0 tool calls**; only at 8192 did a proper tool call with arguments appear.
- **(B) The dedup guard mis-handles never-executed actions.** A malformed call (`invalid_action`, "script is required") correctly does **not** consume the action budget, **but it still feeds the repeat-dedup fingerprint** `(run_python, hash(""), ())`. After `max_repeats=2` the identical empty call is refused as "identical action already attempted," and 6 refusals trip `max_repeats*3` → terminal stall. A recoverable "you forgot the script" becomes a fatal loop, and the refusal message **misdiagnoses** the real cause.

---

## 3. Is CodeAct the right paradigm? (context for the roadmap)

- **Yes — it is a recognised, on-trend industry pattern.** "LLM writes a Python script → run in a sandboxed workspace → observe → repeat" is *code-as-action* (CodeAct) ReAct, where code is the action space instead of one-tool-per-JSON-call.
- **Industry validation:** HuggingFace `smolagents` defaults to a `CodeAgent` for this reason; the CodeAct research line and Anthropic's "code execution with MCP" guidance argue code beats rigid tool schemas for open-ended file/data work.
- **Strengths realised here:** one general action (`run_python` + `libs`) spans documents, spreadsheets, images, archives, data — no per-format tool registry; composition/loops/error-handling come free in the script.
- **The failures above are implementation-harness gaps, not flaws of the paradigm.** The decision to let the executor write and run code is sound; the gap to best-in-class is in the *harness*.
- **Best practice is often hybrid:** structured/function-calling tools for sensitive or well-known operations, code-execution for open-ended wrangling. This repo already embodies that split via `run_uvx` (CLI tools) + `run_python` (code).

---

## 4. Hardening changes to implement next (the "near-perfect CodeAct harness" bar)

> Priority: **P0 = blocking correctness**, **P1 = reliability/quality**, **P2 = safety/scale**. All should be built as **mechanisms** (role/outcome-framed, domain-neutral), not one-off patches.

### 4.1 Token budget for the code-writing step — **P0**

- **Problem:** `max_tokens=1024` truncates any non-trivial script into an empty/partial tool call; the executor (which *writes code*) currently gets **less** headroom than the planner (`orchestrator_max_tokens=4096`).
- **Fix:**
  - Give the executor ReAct `complete()` calls an **explicit, generous** output budget (e.g. a dedicated `executor_max_tokens` ≥ 8192; size it above thinking-budget + expected script length, not a global 1024 default).
  - When extended thinking is enabled, budget **thinking tokens separately** from visible/output tokens so tool-call arguments can't be starved by reasoning.
  - Detect `stop_reason == "max_tokens"` on a tool call and treat it as a **retryable truncation** (raise budget / ask for a shorter script), not as a normal action.
- **Contract:** for a script of length N tokens, the harness must guarantee the model can emit the full `run_python` arguments; truncation is surfaced as an explicit, self-correcting signal.

### 4.2 Action-dedup / malformed-action handling — **P0/P1**

- **Problem:** never-executed `invalid_action` calls poison the repeat fingerprint and produce a misleading "identical action already attempted" stall.
- **Fix:**
  - **Exclude non-executing errors** (`invalid_action`, schema-validation failures — anything that never reached an instrument) from the repeat-dedup fingerprint entirely. Only *actually executed* actions should count toward "you already tried this."
  - **Validate tool-call arguments before fingerprinting** and return a **specific, corrective** observation ("`script` is missing/empty — provide the full source in the `script` field"), distinct from "same script already tried."
  - Add a **малformed-action budget** separate from the repeat budget, with escalating guidance (re-emit with script → switch instrument → `finish` honestly) so a transient truncation self-heals instead of looping.
  - Make the stall/stop reason **diagnostic** (why it stopped: truncation vs genuine repetition vs budget exhausted), surfaced in `step_diagnostics`.

### 4.3 Sandbox boundaries — **P2 (safety, before any untrusted/multi-tenant use)**

- **Current state:** isolated per-run workspace, staged input **copies** (originals untouched), write-to-new-file discipline, path validation (reject absolute/outside-workspace). Good foundation.
- **Gaps to close for best practice:**
  - **Network egress control:** default-deny outbound from `run_python`/`uvx`, allowlist only what a task needs (package installs vs arbitrary calls). Today a model-authored script can reach the network freely.
  - **Resource limits:** CPU time, wall-clock, memory, output size, and max files/bytes written per step — enforced by the sandbox, not just loop budgets.
  - **Filesystem confinement:** run under an OS-level jail/container (or equivalent) so path checks are defence-in-depth, not the only barrier.
  - **Dependency supply-chain:** pin/vet `uvx --with` distributions; guard against typosquat/arbitrary install names emitted by the model.
  - **Secret hygiene:** ensure workspace env carries no tenant secrets/credentials into model-authored code.
- **Contract:** a hostile or buggy script cannot exfiltrate data, exhaust the host, escape the workspace, or mutate originals — verified by tests, not assumed.

### 4.4 Outcome verification — **P1 (this is what makes "succeeded" trustworthy)**

- **Problem:** endpoint `status: succeeded` overstated reality in 2/3 runs (PDF over target; PPTX absent). Signals are not proof.
- **Fix — verify the *contract*, not the log:**
  - **Parse quantitative targets from the request** ("< 100 kB", "one object per row", "one slide per heading") into a **checkable success predicate**, and evaluate it against the real artifact before declaring success.
  - **Existence + shape checks per artifact type:** file exists in workspace, correct type/format opens, and structural assertions (e.g. PPTX slide count == heading count; JSON length == data-row count; PDF size < threshold **and** text still extractable).
  - **Distinguish "produced but off-target" from "succeeded":** return an explicit `outcome: partial` with the measured gap (e.g. "137 kB vs 100 kB target") rather than `succeeded`, and let the loop iterate (compress harder / downsample) until the predicate holds or budget ends.
  - **Never claim an artifact the harness did not confirm exists.** Tie the final answer's claims to verified facts.
- **Contract:** `succeeded` is emitted **iff** the parsed success predicate is objectively satisfied against the produced artifact; otherwise `partial`/`failed` with a measured reason.

---

## 5. Suggested implementation order (next session)

1. **P0 — Token budget** (4.1): unblocks the entire class of longer-script tasks (PPTX and beyond). Smallest change, biggest correctness win.
2. **P0/P1 — Dedup + malformed-action** (4.2): stops false-terminal stalls and makes truncation self-healing.
3. **P1 — Outcome verification** (4.4): makes `succeeded` mean something; closes the "signals ≠ proof" gap that this whole investigation exposed.
4. **P2 — Sandbox boundaries** (4.3): required before exposing code-execution to untrusted input or true multi-tenant load.

**Re-validation for each:** re-run the same three dry-runs (PDF-compress, XLSX→JSON, MD→PPTX) plus one over-target case, and confirm the harness reports `succeeded` **only** when independent artifact checks pass.

---

## 6. Design principles to hold to (so fixes generalise)

- **Contracts over anecdotes:** state what must be true when done; verify outcomes, not self-report.
- **Mechanisms, not patches:** fix the *class* (any long script, any malformed action, any output format), not the PPTX instance.
- **Core stays domain-neutral:** no format/tool/error-string special-cases in shared prompts or the loop; specifics live at the edges.
- **Exploration ≠ delivery:** a run isn't done until the contracted outcome is met and independently confirmed.

---

## Appendix — Environment notes (as observed)

- API server: `uvicorn api.app.main` (dev, `--reload`) on `:8000`; multiple duplicate dev instances were running on other ports.
- Model: `claude-sonnet-5` for both `fast` and `capable` tiers; `llm_max_tokens=anthropic_max_tokens=1024`; `orchestrator_max_tokens=4096`.
- Loop budget (`react.py::StepBudget`): `max_actions=12`, `max_rounds=16`, `max_repeats=2`, refusal stop at `max_repeats*3 = 6`.
- Backing infra (Docker, left running): `csa-postgres`, `csa-redis`, `csa-qdrant`, `csa-tei` (+ `ncp-postgres`).
- App services (uvicorn/celery/next/ngrok) are launched by **Cursor IDE terminals** that auto-restart them on exit; stopping them permanently requires closing those terminals in the IDE, not killing PIDs.
