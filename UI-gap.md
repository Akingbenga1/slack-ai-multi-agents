# UI gaps

Walked admin and org portal pages in the browser and compared them to `docs/portal.md` and `docs/admin-portal.md`.

## Already covered (core routes exist)

- Admin: Overview, Tenants, New tenant, Tenant detail, Health, Billing, Tools.
- Org: Overview, Agent, Tools, Knowledge, Workflows, Billing, Usage, Slack, Invite, Signup, Login.

## Fixed

1. **Sign out** — Sign out button added to the admin and org dashboard sidebar footer.
2. **Invite as a real portal page** — Create-invite UI lives at `/app/invite` inside the org shell; `/invite?token=…` remains the public accept link.

## Still missing or incomplete (UI, not “API not connected”)

3. **Team / Members page** — you can create invite links, but there is no page to list members, pending invites, or remove access.
4. **Edit tool page** — you can create and remove tools, but there is no edit page for an existing tool.
5. **“Save to tool registry” after discovery** — discovery has Discover/Use, then Create tool; there is no clear save-from-discovery step.
6. **Platform audit log page** — audit entries only appear on tenant detail; there is no `/admin/audit` overview.
7. **Admin deep links into tenant ops** — tenant detail links to Tools and Billing, but not to that tenant’s Agent, Knowledge, Usage, or Slack views.
8. **Dedicated “Add MCP server” page** (optional) — MCP servers are only added inline on the tools list.

## Not required as new portal pages by current docs

- Onboarding stays a Slack stub.
- Day-to-day Q&A / document summary stays in Slack, not a new web page.
