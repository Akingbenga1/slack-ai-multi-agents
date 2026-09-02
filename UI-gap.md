# UI screens

Short list of every web UI screen, grouped by role.

Prototype design files can be found under the `prototype-design` folder in the root of this project.

**Demo tenant id:** `11111111-1111-1111-1111-111111111111` (tenant routes). Foreign id for 403 test: `22222222-2222-2222-2222-222222222222`.

**Legend — Implemented (new UI):**

| Value | Meaning |
| ----- | ------- |
| **Yes** | New dashboard shell + `PageHeader` + content uses the new design system (`ui/card`, `ui/button`, Tailwind tokens). Matches prototype where one exists. |
| **Partial** | New dashboard shell + `PageHeader` only; main panel/content still uses legacy inline styles or old CSS modules. |
| **No** | Legacy public/auth pages — no dashboard shell, inline styles. |

---

## Section 1 — Platform owner UI (`/admin`)


| Screen              | Path                                             | Open                                                                                                                                                                                           | What it is for                                                                | Prototype design   | Implemented (new UI) |
| ------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------------ | -------------------- |
| Admin overview      | `/admin`                                         | [http://localhost:3000/admin](http://localhost:3000/admin)                                                                                                                                     | Home dashboard — links to tenants, billing, tools, health, and support tasks. | admin Overview.png | **Yes**              |
| Tenant list         | `/admin/tenants`                                 | [http://localhost:3000/admin/tenants](http://localhost:3000/admin/tenants)                                                                                                                     | See all organisations — plan, Slack status, last sync.                        | Tenant list.png    | **Yes**              |
| New tenant          | `/admin/tenants/new`                             | [http://localhost:3000/admin/tenants/new](http://localhost:3000/admin/tenants/new)                                                                                                             | Create an organisation with org admin, billing row, and default agent config. | New Tenant.png     | **Yes**              |
| Tenant detail       | `/admin/tenants/[tenantId]`                      | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111)                                           | One tenant — suspend/unsuspend, plan waiver, budgets, audit log, deep links.  | Tenant Details.png | **Yes**              |
| Tenant agent        | `/admin/tenants/[tenantId]/agent`                | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/agent](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/agent)                               | View/edit that tenant’s agent name, prompt, allowlist, and schedules.         | Tenant agent.png   | **Yes**              |
| Tenant knowledge    | `/admin/tenants/[tenantId]/knowledge`            | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/knowledge](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/knowledge)                       | That tenant’s uploads, ingest jobs, files, and Slack sync.                    |                    | **Yes**              |
| Tenant usage        | `/admin/tenants/[tenantId]/usage`                | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/usage](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/usage)                               | That tenant’s mentions, jobs, errors, and token usage.                        |                    | **Yes**              |
| Tenant Slack        | `/admin/tenants/[tenantId]/slack`                | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/slack](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/slack)                               | That tenant’s Slack workspace connection status and connect flow.             |                    | **Yes**              |
| Tenant tools        | `/admin/tenants/[tenantId]/tools`                | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/tools](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/tools)                               | Register and manage CLI/MCP tools for that tenant.                            |                    | **Yes**              |
| New tenant tool     | `/admin/tenants/[tenantId]/tools/new`            | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/tools/new](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/tools/new)                       | Create a CLI, MCP, or HTTP tool for that tenant.                              |                    | **Yes**              |
| Tenant billing      | `/admin/tenants/[tenantId]/billing`              | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/billing](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/billing)                           | Billing overview for one tenant — plan and payment links.                     | Tenant billing.png | **Yes**              |
| Tenant invoices     | `/admin/tenants/[tenantId]/billing/invoices`     | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/billing/invoices](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/billing/invoices)         | Invoice history for that tenant.                                              |                    | **Yes**              |
| Tenant transactions | `/admin/tenants/[tenantId]/billing/transactions` | [http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/billing/transactions](http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111/billing/transactions) | Payments and adjustments for that tenant.                                     |                    | **Yes**              |
| Platform billing    | `/admin/billing`                                 | [http://localhost:3000/admin/billing](http://localhost:3000/admin/billing)                                                                                                                     | Cross-tenant billing summary.                                                 |                    | **Yes**              |
| Platform tools      | `/admin/tools`                                   | [http://localhost:3000/admin/tools](http://localhost:3000/admin/tools)                                                                                                                         | Cross-tenant tools overview.                                                  |                    | **Yes**              |
| New platform tool   | `/admin/tools/new`                               | [http://localhost:3000/admin/tools/new](http://localhost:3000/admin/tools/new)                                                                                                                 | Create a tool (platform-level tools UI).                                      |                    | **Yes**              |
| MCP host            | `/admin/mcp-host`                                | [http://localhost:3000/admin/mcp-host](http://localhost:3000/admin/mcp-host)                                                                                                                   | Check MCP servers and linked registry tools on the host.                      |                    | **Yes**              |
| CLI host            | `/admin/cli-host`                                | [http://localhost:3000/admin/cli-host](http://localhost:3000/admin/cli-host)                                                                                                                   | Check/install CLI tools on the host (page exists; not in sidebar menu).       |                    | **Yes**              |
| Agent trace         | `/admin/agent-trace`                             | [http://localhost:3000/admin/agent-trace](http://localhost:3000/admin/agent-trace)                                                                                                             | Inspect recent agent runs across tenants.                                     |                    | **Yes**              |
| Platform health     | `/admin/health`                                  | [http://localhost:3000/admin/health](http://localhost:3000/admin/health)                                                                                                                       | API/deep health, job errors, and usage error rates.                           |                    | **Yes**              |




**Sign-in:** [http://localhost:3000/login](http://localhost:3000/login) → [http://localhost:3000/admin](http://localhost:3000/admin) (`owner@example.com` / `owner123` after demo seed).

---



## Section 2 — Organisation representative UI (`/app` and public entry)



### Public entry (before or outside the org portal)


| Screen        | Path              | Open                                                         | What it is for                                                               | Prototype design | Implemented (new UI) |
| ------------- | ----------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------- | ---------------- | -------------------- |
| Site home     | `/`               | [http://localhost:3000/](http://localhost:3000/)             | Landing page — links to sign in or create an organisation.                   |                  | **Yes**              |
| Sign in       | `/login`          | [http://localhost:3000/login](http://localhost:3000/login)   | Email/password login → org admin goes to `/app`.                             |                  | **Yes**              |
| Sign up       | `/signup`         | [http://localhost:3000/signup](http://localhost:3000/signup) | Self-serve registration — creates org + org admin, then opens `/app`.        |                  | **Yes**              |
| Accept invite | `/invite?token=…` | [http://localhost:3000/invite](http://localhost:3000/invite) | Public page to join an **existing** org (add real `?token=` from Team page). |                  | **Yes**              |




### Org portal (signed-in org admin)


| Screen             | Path                        | Open                                                                                                                                 | What it is for                                                          | Prototype design | Implemented (new UI) |
| ------------------ | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------- | ---------------- | -------------------- |
| Overview           | `/app`                      | [http://localhost:3000/app](http://localhost:3000/app)                                                                               | Home — shortcuts to all areas and setup banners (billing, Slack, sync). |                  | **Yes**              |
| Agent              | `/app/agent`                | [http://localhost:3000/app/agent](http://localhost:3000/app/agent)                                                                   | Agent display name, system prompt, channel allowlist, job schedules.    |                  | **Yes**              |
| Tools              | `/app/tools`                | [http://localhost:3000/app/tools](http://localhost:3000/app/tools)                                                                   | List CLI/MCP tools and MCP servers for this organisation.               |                  | **Yes**              |
| New tool           | `/app/tools/new`            | [http://localhost:3000/app/tools/new](http://localhost:3000/app/tools/new)                                                           | Create a tool (with optional discovery prefill).                        |                  | **Yes**              |
| Knowledge          | `/app/knowledge`            | [http://localhost:3000/app/knowledge](http://localhost:3000/app/knowledge)                                                           | Upload files, watch ingest, browse tenant files, trigger Slack sync.    |                  | **Yes**              |
| Workflows          | `/app/workflows`            | [http://localhost:3000/app/workflows](http://localhost:3000/app/workflows)                                                           | Shared workflow library from Slack uploads.                             |                  | **Yes**              |
| Billing            | `/app/billing`              | [http://localhost:3000/app/billing](http://localhost:3000/app/billing)                                                               | Subscribe, manage payment method, plan status.                          |                  | **Yes**              |
| Invoices           | `/app/billing/invoices`     | [http://localhost:3000/app/billing/invoices](http://localhost:3000/app/billing/invoices)                                             | This org’s invoice list.                                                |                  | **Yes**              |
| Transactions       | `/app/billing/transactions` | [http://localhost:3000/app/billing/transactions](http://localhost:3000/app/billing/transactions)                                     | This org’s payment activity.                                            |                  | **Yes**              |
| Usage              | `/app/usage`                | [http://localhost:3000/app/usage](http://localhost:3000/app/usage)                                                                   | Mentions, jobs, errors, and token usage for this org.                   |                  | **Yes**              |
| Slack              | `/app/slack`                | [http://localhost:3000/app/slack](http://localhost:3000/app/slack)                                                                   | Connect or reinstall the Slack app for this workspace.                  |                  | **Yes**              |
| Team               | `/app/team`                 | [http://localhost:3000/app/team](http://localhost:3000/app/team)                                                                     | Members, pending invites, invite new org admins, remove access.         |                  | **Yes**              |
| Invite redirect    | `/app/invite`               | [http://localhost:3000/app/invite](http://localhost:3000/app/invite)                                                                 | Redirects to `/app/team`.                                               |                  | **Yes**              |
| Tenant scope check | `/app/t/[tenantId]`         | [http://localhost:3000/app/t/22222222-2222-2222-2222-222222222222](http://localhost:3000/app/t/22222222-2222-2222-2222-222222222222) | Blocks access if URL tenant ≠ session tenant (403 UI).                  |                  | **Yes**              |


**Sign-in:** [http://localhost:3000/login](http://localhost:3000/login) or [http://localhost:3000/signup](http://localhost:3000/signup) → [http://localhost:3000/app](http://localhost:3000/app) (`admin@example.com` / `admin123` after demo seed).

---

## Summary

_Audit: 2026-09-02 — each screen checked against its page + main content panel for `PageHeader`, dashboard shell, and `ui/card` / Tailwind design tokens vs inline styles or CSS modules._

| Area | Full new UI | Partial (shell only) | Not started |
| ---- | ----------- | -------------------- | ----------- |
| Admin `/admin` | 20 screens | 0 screens | 0 |
| Org `/app` | 14 screens | 0 screens | 0 |
| Public auth | 4 screens | 0 | 0 |

**Prototype coverage:** all six admin screens with PNG mocks in `prototype-design/` are **Yes** (overview, tenant list, new tenant, tenant detail, tenant agent, tenant billing).

**Shared new UI building blocks:** `AdminDashboardShell`, `OrgDashboardShell`, `PublicAuthShell`, `PageHeader`, `ui/card`, `ui/button`, `ui/badge`, dashboard icons.

**Section 2 complete:** all public entry and org portal screens use the new design system (2026-09-02).
