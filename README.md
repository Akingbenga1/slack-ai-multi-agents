# Client Slack AI Agents

A multi-tenant platform that gives each organisation its own AI assistant in Slack — with separate knowledge, billing, and team access.

**Who this is for:** organisation representatives (admins) who manage their team’s account, and team members who use the assistant in Slack day to day.

---

## What your organisation can do

Plain-English summary of platform capabilities. Each customer organisation (tenant) gets its own isolated space.

### AI assistant in Slack

- **Ask questions in Slack** — team members message the bot in channels or DMs and get answers grounded in your organisation’s knowledge.
- **Work with attached files** — upload a PDF, spreadsheet, or other file in Slack; the agent can analyse it, summarise it, or turn results into a PDF reply.
- **Scheduled digests and reports** — set up recurring summaries or reports that post automatically to a Slack channel.
- **Import Slack history** — bring past channel messages into the knowledge base so the assistant can search older conversations.

### Knowledge base

- **Upload company documents** — PDF, Word, Excel, CSV, text, and Slack export files can be ingested and searched.
- **Search with citations** — answers can point back to the source chunks so staff can verify information.
- **Tenant-safe isolation** — your organisation’s documents are never mixed with another customer’s data.

### Organisation portal (web)

Sign in at the web app to manage your account without using Slack:

- **Overview** — see account status at a glance.
- **Agent** — configure and test how the AI assistant behaves for your team.
- **Knowledge** — upload and track document ingestion.
- **Workflows** — browse and save reusable workflow templates for common tasks.
- **Tools** — discover, register, and manage CLI and MCP tools the agent can use.
- **Slack** — connect or review your Slack workspace installation.
- **Usage** — view consumption, rate limits, and budget-related activity.
- **Billing** — manage subscription and payment through Stripe.
- **Invite team members** — create invite links so colleagues can join your organisation.

### Teams and access

- **Multi-tenant teams** — many organisations share one platform; each has its own users, data, Slack install, and billing.
- **Self-service signup** — a new organisation can register and get its own workspace.
- **Role-based access** — organisation admins manage settings; team members use Slack and limited portal features.
- **Invites** — admins generate links to add people to the organisation securely.

### Billing and plans

- **Stripe subscriptions** — checkout, plan status, and customer self-service billing portal.
- **Entitlements per plan** — features can be turned on or off based on what the organisation has paid for.
- **Usage governance** — per-organisation rate limits and budgets help control cost and fair use.

### Behind the scenes (what the platform handles for you)

- **Document ingestion pipeline** — uploaded files are parsed, chunked, embedded, and stored for search.
- **Background jobs** — Slack sync, report delivery, and ingest run on a job queue so the API stays responsive.
- **Agent planning and execution** — the system plans tasks in plain English and can run real command-line tools when needed (e.g. convert or summarise files).
- **Health and operations** — platform owners can monitor service health across all tenants.
