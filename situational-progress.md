# Goal — MCP server install & credentials

## Capability

Tenants can register remote MCP servers (URL + optional service credential or Connect/OAuth), verify readiness before trusting them, and manage those installs through org-rep and Org owner/Platform owner APIs — without secrets leaving encrypted storage.

Org-installed, enabled MCP servers for a tenant are available to Deep Agents on that tenant’s team-member requests when relevant. Control-plane readiness probes stay separate from runtime tool use: probing does not execute user work; Deep Agents may call the same registered servers to satisfy a request.

## Who can do what (MCP install + credentials)

### Organisation reps

- Add an MCP to the tenant client profile as a named connection — usually display name + remote URL (HTTP/SSE/streamable HTTP), sometimes plus transport.
- Can select which installed MCP servers are available on their tenant profile (enable/disable or equivalent selection) for Deep Agents to consider.
- Can list, install, view, update, delete, and readiness-check MCP servers for their own tenant, including optional service credentials or Connect/OAuth tokens that stay encrypted and never returned in full.
- Can Connect (OAuth) for remotes that require industry-standard authorization so OAuth-only servers are usable under the tenant profile.

### Org owner/Platform owner

## Success when

1. A tenant-scoped install stores connection details and encrypted credentials uniquely by name.
2. Install/update can optionally probe readiness and return observable readiness (ready, tool inventory, or error) without exposing the secret.
3. Org-rep and Org owner/Platform owner routes share one install/verify service; control-plane readiness checks remain distinct from Deep Agents runtime invocation of those servers.
4. A different remote MCP backend plugs in at the boundary (URL/credential/transport/OAuth adapter), not by rewriting core install logic.
5. **Org Rep done-when:** a rep can manage unauthenticated, Bearer-authenticated, and Connect/OAuth MCP installs for their tenant from the real UI, and a team member’s Deep Agents request in that tenant can use those enabled installs when relevant (tenant-scoped only; requester does not attach MCPs).
6. **Auth done-when (Bearer still supported):** optional service/API token stored encrypted and sent as `Authorization: Bearer` on verify and runtime use; secret never returned in full — for remotes that accept token/key auth.
7. **Auth done-when (Connect/OAuth — near-term required):** Connect/OAuth is industry-standard and must be implemented for near-term demand (OAuth-class remotes); success when a rep can Connect with name+URL, complete OAuth 2.1+PKCE against Protected Resource Metadata, store refresh/access tokens encrypted, refresh on use, and Deep Agents call that tenant MCP with Bearer access tokens — without hardcoding one vendor and without rewriting the named-connection install boundary. Org Rep goal is not complete for those customers until Connect works.

## Goal implementation

- Completing this goal needs real Org-rep UI (Platform owner UI can wait), Connect/OAuth as a near-term required auth path beside Bearer/unauthenticated, and tenant MCP availability to Deep Agents — UI alone, Bearer alone, or runtime alone is not enough when OAuth-class remotes are in demand.
- Sequence: (1) real Org-rep UI for name+URL, (2) Connect/OAuth with encrypted tokens + refresh, (3) tenant-scoped Deep Agents use; keep Bearer for servers that accept service tokens; do not hardcode specific vendors into core — one remote-auth adapter at the boundary.

### Org-rep UI for MCP install

- Wire the org-rep tools UI to the real tenant MCP APIs (not mock-only state) so a rep can list, install, view, update, delete, and readiness-check MCP servers for their own tenant.
- Rep can select which MCP servers are available on the tenant profile (e.g. enable/disable) so only chosen installs are eligible for Deep Agents.
- Unauthenticated MCP: the UI captures display name + remote URL (and transport when needed), stores no service credential, and can verify readiness with a handshake that sends no Authorization header.
- Authenticated MCP (Bearer): the UI captures display name + remote URL plus optional service/API token; token is stored encrypted, used as Bearer on verify/use, and never returned in full — profile shows connection identity and `has_service_credential` only.
- Authenticated MCP (Connect): the UI offers Connect on the named connection so the rep authorizes OAuth-class remotes; profile shows connected status, not raw tokens.
- Secrets stay out of plain profile text.
- Product promise: add URL → Connect (when required) → select available on tenant → agents may use when relevant.

### Connect/OAuth for authenticated MCP (industry standard — implement near-term)

- Near-term required (not optional polish) so OAuth-only remotes can be installed and used under a tenant.
- UI: Connect flow on the named connection (display name + remote URL) that starts OAuth when the remote challenges or when the rep chooses Connect.
- Discovery: handle `401` + `WWW-Authenticate` / Protected Resource Metadata (RFC 9728) to find the authorization server and required scopes.
- Client auth: OAuth 2.1 with PKCE; resource indicator for the MCP server URL; client identity via Client ID Metadata Documents (or supported registration path).
- Token handling: exchange code for access (+ refresh) tokens; store tokens encrypted per tenant connection; never show raw tokens in the profile UI.
- Runtime: on verify and Deep Agents use, send `Authorization: Bearer <access_token>`; refresh when expired; re-Connect when refresh fails.
- Tenant scope: tokens and Connect state stay on the org/tenant MCP profile; team members do not run their own Connect for each request.
- Boundary: plug OAuth at the credential/adapter edge of the same named-connection install model — do not rewrite core tenant install or Deep Agents tenant selection; do not encode one vendor into shared core.
- Complexity remains real (consent, discovery, refresh, failure UX), but deferring Connect blocks near-term OAuth-class MCP demand — implement it in the Org Rep near-term path; cut Platform-owner UI before cutting Connect if scope must shrink.

### Org owner/Platform owner UI for MCP install

- Wire the Org owner/Platform owner tools UI to the real admin MCP APIs so they can choose a tenant and list, install, view, update, delete, readiness-check, approve, and decline that tenant’s MCP servers, with optional service credentials never returned in full and mutating actions audited.
- Lower near-term priority than Org-rep UI + Connect/OAuth + Deep Agents tenant use if scope must be cut.

### Tenant MCP in Deep Agents execution

- The API can already install MCP servers with or without service credentials, but install alone is not enough: tenant-registered MCP servers selected as available by the Org Rep must be loadable by Deep Agents at run time.
- Org Reps (not individual team members) install and select MCPs on the organisation/tenant profile; a team member’s request runs in that tenant’s context — MCP tools are available when relevant, not guaranteed for every request; the requester does not attach MCPs themselves.
- For each user request, Deep Agents must only see the MCP set the Org Rep made available for that tenant, so one tenant’s servers are never mixed into another tenant’s run.
- After listing tools from those available tenant MCP servers, Deep Agents should use only the MCP tools necessary to do the work — not invoke every listed tool by default.
- Runtime must present a valid access credential for the connection type: none, static Bearer service token, or refreshed OAuth access token from Connect.
- Logging/trace: for each user request, record which MCP server and which tool was used, and where in the run it was used (request/run id, tenant, server name, tool name, step/time) without logging secrets.
- That runtime availability does not replace the Org-rep UI and Connect/OAuth work above; UI manageability, Connect where required, selection of available MCPs, necessary-tool use, and tenant-scoped runtime use are all required.
- Observable Org Rep outcome: after a rep installs (and Connects when required) and selects an MCP as available, a team-member request in that tenant can invoke necessary tools from that server when relevant; a request for another tenant cannot; traces show which MCP/tool ran on that request.
