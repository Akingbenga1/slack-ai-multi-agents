---
name: dtc-ralph-loop
description: >-
  Ralph-loop for the DTC AI/automation stack using Project-Documents/jira-task.md,
  Sprints/ folders, task journals, project-wide progress.md, 3-task batches, and
  Needs-human blockers. Use when the user asks to run the Ralph loop,
  continue a sprint, or resume from progress.md.
---

# Ralph Loop 

This project uses the **Ralph loop**: work in bounded agent sessions, persist state on disk, resume from checkpoints — never restart from scratch if progress exists.

---

## Source of truth

All planning and requirements docs live under **`Project-Documents/`**. Do not look for them at the project root.

- **`Project-Documents/jira-task.md` is the source of truth and task instruction** for every Ralph loop run. It defines what to build: sprints, tasks, order, descriptions, cross-cutting rules, and exit criteria. Work from it directly — do not invent tasks, reorder sprints, or guess scope beyond it.
- **If `Project-Documents/jira-task.md` is missing** but `Project-Documents/raw-project-description.md` is present (and has content): **ask the user for permission** to create `jira-task.md`. Do not create it until they approve. After approval, derive the full sprint/task plan from the details in `Project-Documents/raw-project-description.md` and write `Project-Documents/jira-task.md` in this project only — never copy or reuse `jira-task.md` (or other source docs) from a sibling/other project.
- For requirements context (commercial ops model, what each build serves, locked stack), follow docs in `Project-Documents/` (e.g. `technology-stack-document.md`, `architecture-description.md`, `user-stories.md`, `industry-practice.md`). Prefer those over guessing why a task exists.
- For architecture and tool details (APIs, RAG patterns, integration options), follow `Project-Documents/architecture-description.md` and `Project-Documents/technology-stack-document.md`. Prefer those over guessing schemas, endpoints, or vendor choices.

### Project-Documents contents

```
Project-Documents/
  jira-task.md                      # sprint/task plan (source of truth)
  raw-project-description.md        # original client brief
  architecture-description.md
  technology-stack-document.md
  user-stories.md
  industry-practice.md
  sacalabilty-problems.md
```

---

## Folder layout

`Sprints/` lives at project root (alongside `Project-Documents/`). Create sprint/task subfolders as work starts.

```
Project-Documents/                # planning docs (see above)
Sprints/
  progress.md                     # PROJECT-WIDE resume checkpoint (all sprints)
  Sprint 1/
    progress.md                   # sprint-local detail
    Task 1.1/
      task1.1.md
      task1.1-journal.md          # only when completed / interrupted / needs human
    Task 1.2/
      task1.2.md
      ...
  Sprint 2/
    progress.md
    Task 2.1/
      ...
  ...
```

Sprint folder names follow `Project-Documents/jira-task.md` (e.g. `Sprint 1`, `Sprint 2`, …).

Task subfolder names match task IDs in `Project-Documents/jira-task.md` (e.g. `Task 1.1`, `Task 2.3`).

---

## Progress checkpoints

### Project-wide — `Sprints/progress.md` (required)

Single resume entry point across **all** sprints. Read this first at the start of every Ralph loop run. Create it on first run if missing.

Keep it updated with:

- Active sprint
- Last completed task (e.g. `1.3`)
- Current / next task (e.g. `1.4`)
- Open **Needs human** items (rollup across sprints)
- Which 3-task batch is in progress
- One-line pointer to the active sprint folder (e.g. `Sprints/Sprint 1/`)

This is the resume checkpoint if the laptop sleeps, the chat ends, or a new agent run starts — especially important with many sprints so the agent does not reopen the wrong sprint folder.

### Sprint-local — `Sprints/Sprint N/progress.md`

Same fields scoped to that sprint (task list detail, sprint exit criteria notes). Update whenever the project-wide file is updated for work in that sprint.

---

## Per-task lifecycle

### At task start

1. Create the task folder (e.g. `Sprints/Sprint 1/Task 1.1/`).
2. Create **`task1.1.md`** immediately — before implementation.
   - Expand `Project-Documents/jira-task.md` bullets into an exact steps checklist.
   - Include acceptance criteria for this task.
   - Check off items as work proceeds.

### When task ends (any of these)

Create **`task1.1-journal.md`** when the task is:

- **Completed**, or
- **Interrupted** (session ends, context limit, laptop sleep), or
- **Needs human input** (secrets, client decision, blocked API access)

Do **not** create the journal at task start — only when there is something to record.

### Journal purpose

Capture what was achieved, current status, and handoff data so the next Ralph loop session can resume without re-reading the whole chat.

**Status** (one of): `completed` | `in_progress` | `needs_human` | `blocked`

### Journal headings (use what fits the task)

Always include:

- **Status**
- **Summary** — what happened this session
- **Acceptance criteria checklist** — copy from `taskN.N.md`; mark done / partial / not started
- **Decision log** — architectural or product choices made and why
- **Needs human** — what is required, why, where to put it (if applicable)
- **Files changed** — paths touched
- **Resume notes** — exact next step for the next session
- **Open questions** — unresolved items

Add task-relevant sections when useful, e.g.:

- **Credentials / env vars** (Task 1.5, integration tasks)
- **API / webhook config** 
- **Schema / migration notes** 
- **Smoke test results** (light checks only)
- **Commercial mapping** — which role and pipeline step this task serves (brief → produce → review → revise → launch → learn)

---

## Rules

- Work tasks in dependency order per `Project-Documents/jira-task.md` (sprint order, then task numbers within the sprint). Read `Sprints/progress.md` (project-wide), the active sprint’s `progress.md`, and relevant journals at the start of every run and resume from the next unfinished task — do not restart from Task 1.1 / Sprint 1 if progress already exists.
- Work on at most 3 tasks per agent session to limit context rot. After finishing (or partially completing) that batch of up to 3 tasks, update `Sprints/progress.md`, the active sprint’s `progress.md`, and the relevant journals, then stop and tell me the resume prompt for the next batch (e.g. “Continue Sprint 1 from Task 1.4”).
- For each task: implement what you can → update `taskN.N.md` / `taskN.N-journal.md` → update both progress files → then continue to the next task in this batch while this session is active.
- Do NOT do deep acceptance-criteria verification or long QA loops. Light smoke checks only if quick.
- If blocked on human input (secrets, API credentials, client status map, review-app choice, winning-ad definition, hosting account, etc.): do NOT stop and wait. Record it in the journal under "## Needs human" (what is needed, why, where to put it), mark the task as blocked/partial, update both progress files, then move on to the next task in the batch.
- Keep `Sprints/progress.md` (project-wide) and `Sprints/Sprint N/progress.md` with: last completed, current/next task, open Needs-human items, and which 3-task batch is in progress. The project-wide file is the primary resume checkpoint if the laptop sleeps, the chat ends, or a new agent run starts.
- Prefer continuous progress across sessions over one marathon session. If you stop or the session ends, you must update both progress files and the current task journal with what was completed, what is still open, and any Needs-human items, so the next run can resume accurately.
