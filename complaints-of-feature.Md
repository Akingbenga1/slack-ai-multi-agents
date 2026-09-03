I reviewed both agents, ran the failing scenario myself, and validated a different tooling primitive. Here's the assessment and proposal.

uvx code-execution proof: four PNGs combined

## What you have today

- **The split is already correct**: `orchestrator.py` (548 lines) plans plain-English `execute_goal` steps and never touches tools, while `executor.py` (1,389 lines) loads the persisted plan and runs steps sequentially. Plans and steps persist to `agent_plans` / `agent_plan_steps` / `agent_runs`, so state and tracing are real.
- **A ReAct loop exists** in `_run_english_goal_react` with a 12-attempt budget and a 2-round empty-completion allowance. Its tool surface is `run_uvx`, `write_text_file`, and `write_pdf_text`.
- `uvx_invoke.py` **(1,157 lines) is a "find the right CLI" state machine**: help probes, a probe contract of allowed subcommands and flags, a pending-delivery gate, remediation regexes over uvx stderr, and an attempt ledger. This is the single largest and most fragile piece of the system.
- `outcome_verifier.py` **(526 lines) already verifies observable outcomes**, distinguishing artifact goals from informational ones and excluding attachment files from counting as new artifacts. The instinct there is right and worth keeping.



## Why it is failing (I reproduced it)

- **The strategy itself is the bug, not the tuning.** Your last dry-run, "Combine the 4 png files into one single png image file", burned 8 LLM rounds over 109 seconds and returned `expected observable artifact not verified`.
- **No PyPI console script combines PNGs.** ImageMagick's `montage` is not a PyPI entry point, so the model was asked to find a tool that does not exist and correctly failed after exhausting its budget.
- **The same task is a 12-line Pillow script.** I ran `uvx --with pillow python combine.py` on your four actual `dryrun_*.png` files: it produced a correct 1340×2330 combined PNG in 2 seconds, shown above.
- **The working directory is the shared tenant upload folder.** `_resolve_working_dir` returns the parent of the first attachment, so the verification baseline in your log contained unrelated files like `Valuable_Statistics.xlsx` and `api-test.zip`. Runs pollute shared storage and can collide with each other.
- **Observations are plumbed as** `user` **messages, not** `tool_result` **blocks.** The loop rebuilds the message list each round and prepends a ledger, which breaks provider-native tool pairing, defeats prompt caching, and forces hacks like `_ensure_single_user_continuation`.
- **Completion is inferred from the absence of tool calls**, then reverse-engineered by `_react_success_from_attempts`. There is no explicit terminal action, so "model went quiet" and "model finished" are indistinguishable.



## The proposal: code execution as the uvx tool surface

- **Capability contract first.** Given a request plus zero or more attachments, the system must produce the requested observable outcome — a new valid artifact on disk, or a grounded informational answer — using only uvx-provisioned tooling, within bounded attempts and wall-clock, independently verified rather than self-reported.
- **Make** `run_python` **the primary tool.** The model writes a Python script, the executor writes it into the run workspace, then executes `uvx --with <libs> python script.py`. This stays 100% uvx for tooling while being Turing-complete over the entire PyPI library ecosystem.
- **This collapses your whole scenario matrix onto one primitive.** `pypdf`, `pdfplumber`, `python-docx`, `python-pptx`, `openpyxl`, `pandas`, `pillow`, `vobject`, and the stdlib `zipfile`/`json`/`email` modules cover all 25 cases in `system-behaviour.md`. You stop depending on whether a maintainer happened to ship a console script.
- **Keep** `run_cli` **as a secondary tool** for genuinely CLI-shaped work such as `ocrmypdf`, `markitdown`, and `yt-dlp`. Same uvx runner, same result contract, but it is no longer the only road.
- **Add** `inspect_workspace` to list, stat, and head files. Cheap grounding stops the model guessing at paths and formats, which is where several of your attempts were wasted.
- **Add an explicit** `finish` **tool** carrying a structured claim: artifacts produced plus answer text. Never infer termination from silence.
- **Pass scripts as files, never as** `-c`**.** Your `_UNSAFE_ARG` regex blocks `; & | \` $ < >  and newlines, so inline code would be rejected outright. A script file is also auditable, replayable, and trivially attachable to the trace.



## Loop mechanics to fix

- **Use an append-only transcript with real** `tool_use`**/**`tool_result` **pairing.** This restores correct provider semantics and lets prompt caching cut your per-round cost and latency.
- **Terminate on progress, not just attempt count.** Fingerprint each action; if the same fingerprint repeats, force a strategy change rather than spending another identical attempt. Enforce separate attempt, wall-clock, and token budgets.
- **Add one structured reflection turn on failure** (the Reflexion pattern) instead of free-form retries. Feed it the typed error class you already compute in `classify_uvx_tool_result`, which is good and worth preserving.
- **Isolate one ephemeral workspace per run.** Copy attachments in, execute there, diff against an empty baseline, then promote outputs to storage. This fixes artifact verification, concurrency, and cleanup in a single change.
- **Cache verified scripts as reusable skills** keyed by task signature (the Voyager pattern). Replay the known-good script first and fall back to ReAct only on miss, turning your 14-second cold rounds into ~2-second warm ones and making repeat tasks deterministic.
- **Pre-warm the uv cache** for your common library set. Package resolution on first use is a large share of your current per-round latency.



## Industry standards check

- **Your plan-and-execute split matches Anthropic's orchestrator-workers pattern** from "Building effective agents", and the ReAct loop matches Yao et al. Structurally you are on the mainstream path.
- **Code execution as the tool surface is the 2026 consensus**, via Anthropic's [programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) and Cloudflare's Code Mode. Reported token reductions run from 78% to 99% because intermediate data and tool definitions stay out of context.
- **The piece you are missing is the evaluator-optimizer loop**: verify, reflect on the verifier's stated reason, then retry. Today a verification failure ends the run instead of informing a bounded second attempt.
- **Small, well-documented tool surfaces beat large ones** (the SWE-agent agent-computer-interface finding). Four crisp tools will outperform your current probe-contract machinery.
- **Model-generated code raises the security bar**, and [recent research](https://www.arxiv.org/pdf/2602.15945) shows untrusted tool output becomes executable semantics in this design. Mitigate with the isolated workspace, no shell, OS-level resource limits, denied network egress during execution, and no secrets in the child environment.



## Rewrite? No — a targeted replacement

- **Keep** the orchestrator, plan and step persistence, `guardrails.py`, `uvx_runner.py`, the `llm.py` adapters, the admin trace, and the `outcome_verifier.py` core. That is the majority of the subsystem and it is sound.
- **Replace** `_run_english_goal_react` (roughly 700 lines of `executor.py`) and most of `uvx_invoke.py` (1,157 lines). Both exist to make "guess a console script" work, and the code-execution primitive makes that problem disappear.
- **Retire the dead weight** while you are in there: the LangGraph remnants (`state.py`, `checkpointer.py`, `prompts.py`, `workflows/tool_strategies.py`) and the `plan_execute_enabled` flag that no code reads. Either wire `tool_rag.py` into the planner or delete it, since it is built but deliberately bypassed.
- **Net effect is about 1,500 lines swapped behind stable interfaces**, with your existing test suite as the safety net. That is an afternoon-scale refactor per phase, not a rewrite.



## Do you need a verify agent?

- **Yes, you need verification as a distinct role — but mostly as code, not as an agent.** An LLM agent for this is slower, costlier, and less trustworthy than a deterministic check for the things that matter most.
- **Deterministic checks cover the artifact contract**: the file is new relative to the run baseline, non-zero, format-valid by magic bytes, openable by a uvx probe script, of the expected count, and the inputs are unmodified. Your `outcome_verifier.py` already does a good portion of this.
- **Reserve an LLM judge for semantic criteria only**, such as "summary includes decisions and follow-ups". Give it the success criteria plus evidence, no tools, and require a pass/fail with a reason.
- **Independence is what matters**: the verifier must not be the same call that claims success, and its reason string becomes the reflection signal for a bounded retry. Keeping it a function plus a small judge call is the right cost-robustness point.



## Suggested sequencing

- **Phase 1** — per-run isolated workspace plus `run_python`, `inspect_workspace`, and `finish`. This alone should turn your PNG scenario green.
- **Phase 2** — rewrite the loop with proper `tool_result` pairing, progress-based termination, and the reflection turn; retire the probe-contract machinery.
- **Phase 3** — verifier split into deterministic checks plus judge, wired into a bounded verify-retry loop, then the skill cache and cache pre-warming.
- **Phase 4** — run all 25 `system-behaviour.md` scenarios live as the acceptance gate, since that document is your real contract.

Want me to switch to Plan mode and write this up as a concrete implementation plan with file-level diffs, or start directly on Phase 1?

Phases 1 and 2 are done, tested, and verified live.

## What I built

- `api/app/agent/workspace.py` **(291 lines) — isolation.** Each run gets one workspace under `data/workspaces/<tenant>/<plan_id>`, with declared inputs copied in as staged files. Originals can no longer be mutated in place, and artifact detection compares against a baseline containing only your inputs.
- `api/app/agent/code_exec.py` **(395 lines) — the tooling primitive.** `run_python` writes the model's script into the workspace and runs `uvx --with <libs> python script.py`, so any PyPI library is reachable while tooling stays 100% uvx. `run_cli` keeps the console-script path, and both return one shared observation contract.
- `api/app/agent/react.py` **(765 lines) — the loop.** Four actions only: `run_python`, `run_uvx`, `inspect_workspace`, and `finish`. Termination is explicit via `finish`; the loop otherwise stops only on a spent budget or detected stalling.
- `api/app/agent/llm.py` **— correct tool plumbing.** Added a provider-neutral transcript (`assistant_action_message`, `tool_observation_message`) with mappers to Anthropic content blocks and OpenAI function calls. Observations are now real `tool_result` blocks paired to their `tool_use` id, not user messages.



## Behaviours that fixed the failure mode

- **Budget accounting separates executed actions from refusals.** Empty model turns and refused repeats no longer consume the action budget, so a step keeps its chances to make progress.
- **Identical actions are refused without running.** Fingerprinting covers script text, libs, package, args, and flags; after the repeat allowance the loop is told to change instrument rather than re-run.
- **A run of failures triggers one structured self-review** before more attempts, and typed `error_class` values drive it. `ModuleNotFoundError` becomes an actionable "add this distribution to libs" hint rather than an opaque failure.
- **A** `finish` **claim is adjudicated, not trusted.** Naming artifacts that do not exist fails the step, and `outcome_verifier` still has the final say. I caught this gap through a failing test I wrote and fixed the logic.
- **The retired probe machinery is gone from the loop.** No help ladder, no pending-delivery gate, no allowed-flag contract; `uvx_invoke` keeps only the useful preflight normalisation and stderr remediation.



## Evidence

- **The scenario that failed now succeeds.** "Combine the 4 png files into one single png image file" previously burned 8 rounds over 109 seconds and returned `expected observable artifact not verified`; it now produces a correct 2×2 grid in 30 seconds.
- **The retained scripts show the intended reasoning**: the model first inspected the four images' sizes, then combined them. Inputs came back byte-identical, and the artifact was promoted to the uploads directory.
- **Two more** `system-behaviour.md` **scenarios pass live.** Splitting a workbook into six per-sheet CSVs exercised the multi-artifact verifier, and a PDF bullet-point summary exercised the informational branch.
- **Zero regressions.** Against a `.env`-matched baseline worktree, the failure set is byte-identical at 10 pre-existing failures, while passing tests went from 174 to 224.
- **The 10 pre-existing failures are unrelated to this work**: `test_compose_isolation`, one facade happy-path test, and `test_llm_config`/`test_llm_factory` tests that break because your local `.env` overrides model ids. Ruff is clean on every file I touched.



## New settings


| Setting                           | Default           | Purpose                            |
| --------------------------------- | ----------------- | ---------------------------------- |
| `agent_workspace_root`            | `data/workspaces` | Where run workspaces live          |
| `agent_workspace_keep`            | `True`            | Retain workspaces for trace replay |
| `agent_python_libs_allowlist`     | `""` (any)        | Restrict injectable libraries      |
| `agent_python_max_libs`           | `8`               | Cap libraries per action           |
| `executor_step_timeout_seconds`   | `900`             | Wall-clock ceiling per step        |
| `executor_reflect_after_failures` | `3`               | Failures before self-review        |
| `executor_max_repeated_actions`   | `2`               | Repeats before refusal             |
| `executor_observation_chars`      | `4000`            | Transcript observation budget      |




## Two things worth knowing

- **Phase 3 is not done**: verification is still the existing heuristic `outcome_verifier`, without the deterministic format/openability checks, the LLM judge for semantic criteria, or the verify-retry loop. That was the plan, but it means a semantically wrong-but-present artifact can still pass.
- `run_python` **executes model-authored code**, which raises the security bar as I flagged earlier. Current mitigations are the workspace confinement, no shell, argument validation, and library policy; OS-level resource limits and denied network egress during execution are not yet in place.

I left `scripts/verify_goal_execution.py` so you can run any request end to end: `python -m scripts.verify_goal_execution "<request>" [input filenames]`. Want me to continue with Phase 3, or add the execution sandboxing first?