# Goal — Tenant skills for Deep Agents

## Capability

Tenant team members can create skills as **`.md` files** from the UI.  
Deep Agents load and run those markdown skills for requests in that tenant.  
Each tenant has one **`catalog.json`** tree (folders + links to skill `.md` files).  
The UI tree and Deep Agents both read that same catalog.  
This feature is **standalone and pluggable** — not tied to the workflow library.  
No hard lock-in: storage and skill-loading stay behind clear boundaries so backends can change later.

## Main users

- **Team member** — creates, edits, moves, deletes, and calls skills for their organisation.
- **Deep Agent** — selects and executes a matching skill when a request needs one.

No separate org-editor role for now. Members own the tenant skill library.

## Storage (per tenant)

Store each tenant’s skills under that tenant’s **blob/file store** (tenant-scoped keys).  
Recommended layout (role names, not one vendor path):

- `{tenant}/skills/catalog.json` — the navigable JSON tree  
- `{tenant}/skills/**/*.md` — skill files (folders mirror the tree)

Why: industry-common pattern is tenant-prefixed object/blob storage; this repo already has a tenant-scoped blob store.  
Keep a thin **skills store** boundary so local disk, S3, or another backend can plug in without rewriting core skill logic.

## Skill files

- A skill is a **`.md` file** (name, description in front matter or header, then steps/instructions).  
- Deep Agents treat **markdown skill files** as the standard skill body (same idea as common agent skill packs that ship `SKILL.md` / `.md` procedures).  
- Folders group skills; they are nodes in `catalog.json`, not separate skill runnables.

## Catalog (`catalog.json`)

- One JSON tree per tenant: folders, order, and pointers to skill `.md` paths.  
- Source of truth for the UI tree view.  
- Members do not hand-edit it for normal create/move/delete.

## Catalog update rule

Every create, move, rename, or delete of a skill file or folder goes through **one write path**.  
That path updates the `.md` (or folder) **and** `catalog.json` together.  
If the write fails, neither change is kept — so the tree does not drift.

## Progressive disclosure (intended)

This skill structure is meant to use **progressive disclosure**.  
First the agent sees only the short catalog index (name + description).  
It loads the full skill `.md` only after a skill is selected.  
It does not put every skill body into context up front.

## How the agent picks a skill (industry pattern)

1. **Explicit** — user names the skill → load that `.md` and run it.  
2. **Described match** — agent sees a short index from the catalog (name + description only).  
3. **Load on use** — only then read the full `.md` (progressive disclosure).  
4. If nothing matches well, ask or continue without a skill — do not force a wrong skill.

## User journey

### 1. Create a skill (UI)

**As a team member,** I open the skills page in the org UI.  
I create a skill as a `.md` file (name, short description, steps).  
I optionally note which tools it may use and what “done” looks like.  
I choose a folder in the tree (or the root).  
On save, the system writes the `.md` **and** updates `catalog.json` in the same step.

### 2. Add a folder

**As a team member,** I add a folder in the skills tree.  
On save, `catalog.json` gains that folder.  
New skills can sit under it when created or moved.

### 3. Edit or move a skill

**As a team member,** I open an existing skill `.md` and edit it.  
If I rename or move it, `catalog.json` updates in the same step.

### 4. Browse the skill tree

**As a team member,** I see folders and skills from `catalog.json`.  
I open a skill to view or edit its `.md`.  
I cannot see other tenants’ skills.

### 5. Delete a skill or folder

**As a team member,** I delete a skill `.md` or a folder.  
Deleting a folder removes or relocates its children per UI choice (confirm first).  
On confirm, files change **and** `catalog.json` updates in the same step.

### 6. Call a skill

**As a team member,** I ask the Deep Agent by skill name or in plain language.  
The agent uses the catalog index to pick a skill, then loads that `.md`.  
It follows the skill and only the tools the run is allowed to use.

### 7. Agent executes the skill

**As the Deep Agent,** I load the selected tenant `.md` skill.  
I follow its steps against the user’s request.  
I stop when the skill’s success checks are met (or report failure clearly).

### 8. See what ran

**As a team member,** I can see that a skill ran for my request.  
The trace shows skill name/path (and version if present) and tools used.  
Secrets are never shown.

## Pluggable / no lock-in

- Skills feature is its own module: store, catalog, UI, and agent skill-loader.  
- Agent harness calls a **skill provider** interface — swap storage or matching later without rewriting the centre.  
- Not coupled to the workflow library in this goal.

## Done when

1. A member can create and save a skill `.md` from the UI for their tenant.  
2. A member can add folders and see a tree from `catalog.json`.  
3. Create / move / rename / delete of a skill or folder updates `catalog.json` in the same step.  
4. A member can edit tenant skill `.md` files.  
5. A member can invoke a skill by name or natural language via the Deep Agent.  
6. The agent picks via catalog index, then loads the full `.md` only when selected.  
7. Skills live in tenant-scoped blob/file storage behind a pluggable boundary.  
8. Another tenant never sees or runs those skills.  
9. A run leaves a simple audit trail (skill + tools), not just a chat reply.
