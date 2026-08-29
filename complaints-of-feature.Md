# Agent success verification and evals

Industry practice has moved away from “the model said success” or “the tool returned exit 0.” Production agents are judged on **environment state** and **task contracts**, not log lines alone.

---

## 1. Outcome / state verification (most important)

Harbor, agent sandboxes, and BFCL-style evals score agents by **inspecting the filesystem after the run** — file exists, correct path, correct content — not by CLI stdout.

**Example from this project:** `Combined.pdf` was in `checker/` but the API said `failed`. Industry fix: a **post-step verifier** that checks disk against success criteria before marking a step or run failed.

---

## 2. Deterministic checks first, LLM judge second

Standards like the Agentic Product Standard say: **code-based checks first** (file path, size, hash, page count), then an LLM judge only for fuzzy goals.

The executor should not be the only judge of its own success.

---

## 3. Portable success contracts (eval manifests)

ECP-style thinking: each task defines **inputs, expected artifacts, and verifiers** in a small contract the orchestrator and evals share.

That is the structured “picture of success” — not prose in a prompt, but **checkable expectations** (e.g. “PDF exists under `checker/`”).

---

## 4. Agent evals: two layers

- **End-to-end:** Did the user goal succeed on disk?
- **Step / trajectory:** Were tools reasonable, retries bounded, no false success on `--help`?

Braintrust and LangSmith both support **datasets + scorers** on traces. LangChain AgentEvals adds trajectory matching and LLM judges on top.

---

## 5. Grade trajectories, not only final answers

Claw-Eval and similar work show **final-answer-only grading misses a lot** — safety issues, wrong paths, lucky outcomes.

Scorers should cover:

- Tool choice
- **`help_only` mistaken for work**
- Step 0 doing step 1’s job
- Empty LLM turns on later steps

---

## 6. Use pass^k, not pass@k, in evals

Research stress: **succeed once in 3 tries (pass@k)** hides fragility; production cares about **succeed every time (pass^k)**.

Run each eval scenario **multiple times** — merge PDF, merge + move to folder, etc.

---

## 7. Golden datasets from real failures

Turn production failures into eval cases:

- Merge only
- Merge + move to `checker/`
- Multi-step with prior handoff

Each case gets **filesystem assertions** (and optionally pytest + LangSmith).

---

## 8. Concrete suggestions for this stack

- After each `execute_goal`, run a **small verifier**: list cwd, assert expected files.
- Treat **`uvx exit 0 + help text`** as not done — distinguish probe vs produce.
- **Plan-level success:** if the **final user goal** is satisfied on disk, don’t fail the whole run because a later step stalled.
- **Cap ReAct retries** and score **attempt count** in evals (too many tools = fail or warn).
- Log **environment snapshot** (file listing) at step boundaries for eval replay.

---

## 9. Eval tooling to look at

| Tool | Role |
|------|------|
| **Harbor + Braintrust** | Sandbox tasks + filesystem verifiers synced to experiments |
| **LangSmith + AgentEvals** | Trajectory datasets, pytest integration |
| **Custom pytest** | Extend existing tests (e.g. `test_step_handoff.py`) with **end-state file checks** after simulated agent runs |

---

## Bottom line

Industry standard is **“trust the environment, not the agent’s self-report.”**

Prompts and handoff help, but **evals + deterministic verifiers on disk state** are what stop repeated false failures when the merge/move actually worked on disk.
