"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import panel from "@/components/dashboard/panel.module.css";
import styles from "@/components/tools/tools.module.css";
import { ToolDiscoveryPanel } from "@/components/tools/ToolDiscoveryPanel";
import { McpToolDiscoveryPanel } from "@/components/tools/McpToolDiscoveryPanel";
import { ApiError, apiClient } from "@/lib/api";
import {
  createMockTool,
  getMockMcpServers,
  getMockTools,
  type MockToolKind,
} from "@/lib/mock/tools-data";

type CreateKind = "cli" | "mcp" | "http";

type TenantOption = {
  id: string;
  name: string;
  slug: string;
};

type Props = {
  cancelHref: string;
  accessToken?: string | null;
  /** Org session tenant, or admin-selected tenant for X-Client-Id. */
  tenantId?: string | null;
  tenantLabel?: string;
  tenants?: TenantOption[];
  initialTenantId?: string;
};

type ToolCreateResponse = {
  id: string;
  name: string;
  kind: string;
  mcp_server_id?: string | null;
};

type McpDiscoverySelection = {
  id: string;
  name: string;
  source: string;
  metadata: Record<string, unknown>;
};

function buildCliConfig(
  command: string,
  discovered: Record<string, unknown> | null,
): Record<string, unknown> {
  const base =
    discovered && typeof discovered === "object" ? { ...discovered } : {};
  const args = Array.isArray(base.args) ? base.args : [];
  const subcommands =
    base.subcommands &&
    typeof base.subcommands === "object" &&
    !Array.isArray(base.subcommands)
      ? base.subcommands
      : {};
  return {
    ...base,
    command: command.trim(),
    args,
    subcommands,
  };
}

function normalizeMcpTransport(raw: unknown): string {
  const t = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (t === "stdio" || t === "std-io" || t === "standard-io") return "stdio";
  if (
    t === "http" ||
    t === "streamable-http" ||
    t === "sse" ||
    t === "websocket"
  ) {
    return "http";
  }
  return t || "http";
}

function buildMcpConnectionConfig(
  selection: McpDiscoverySelection,
): Record<string, unknown> {
  const meta = selection.metadata;
  const remotes = Array.isArray(meta.remotes) ? meta.remotes : [];
  const packages = Array.isArray(meta.packages) ? meta.packages : [];
  const firstRemote =
    remotes.find((r) => r && typeof r === "object") ?? null;
  const remoteUrl =
    firstRemote &&
    typeof firstRemote === "object" &&
    typeof (firstRemote as { url?: unknown }).url === "string"
      ? (firstRemote as { url: string }).url
      : null;
  return {
    registry_id: selection.id,
    source: selection.source,
    url: remoteUrl,
    repository:
      typeof meta.repository === "string" ? meta.repository : null,
    websiteUrl:
      typeof meta.websiteUrl === "string" ? meta.websiteUrl : null,
    version: typeof meta.version === "string" ? meta.version : null,
    remotes,
    packages,
  };
}

async function resolveSessionAccessToken(): Promise<string | null> {
  try {
    const res = await fetch("/api/auth/session", { credentials: "same-origin" });
    if (!res.ok) return null;
    const data = (await res.json()) as { accessToken?: string | null };
    return typeof data.accessToken === "string" && data.accessToken
      ? data.accessToken
      : null;
  } catch {
    return null;
  }
}

function saveErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Sign in to save tools.";
    if (err.status === 409) {
      return err.message || "A tool with this name already exists.";
    }
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

const KIND_CARDS: Array<{
  id: CreateKind;
  title: string;
  text: string;
  badge: string;
}> = [
  {
    id: "cli",
    title: "CLI tool",
    text: "Run a shell command the agent can invoke on demand.",
    badge: "Command",
  },
  {
    id: "mcp",
    title: "MCP tool",
    text: "Expose a capability from a connected MCP server.",
    badge: "Protocol",
  },
  {
    id: "http",
    title: "HTTP request",
    text: "Call a REST endpoint with method, URL, and payload.",
    badge: "API",
  },
];

const KIND_TONE: Record<CreateKind, string> = {
  cli: styles.kindToneCli,
  mcp: styles.kindToneMcp,
  http: styles.kindToneHttp,
};

function KindIcon({ kind }: { kind: CreateKind }) {
  if (kind === "cli") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
        <polyline points="4 17 10 11 4 5" />
        <line x1="12" y1="19" x2="20" y2="19" />
      </svg>
    );
  }
  if (kind === "mcp") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <path d="M14 17.5h7M17.5 14v7" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a14 14 0 0 1 0 18" />
      <path d="M12 3a14 14 0 0 0 0 18" />
    </svg>
  );
}

export function CreateToolForm({
  cancelHref,
  accessToken = null,
  tenantId: tenantIdProp = null,
  tenantLabel,
  tenants,
  initialTenantId,
}: Props) {
  const router = useRouter();
  const showTenantPicker = Boolean(tenants?.length);
  const defaultTenantId =
    initialTenantId ?? tenants?.[0]?.id ?? tenantIdProp ?? "";
  const [tenantId, setTenantId] = useState(defaultTenantId);
  const selectedTenant =
    tenants?.find((tenant) => tenant.id === tenantId) ??
    (tenantLabel
      ? { id: tenantId || tenantIdProp || "", name: tenantLabel, slug: "" }
      : null);
  const effectiveTenantId = (tenantId || tenantIdProp || "").trim() || null;
  const mcpServers = getMockMcpServers(tenantId);
  const existing = getMockTools(tenantId);

  const [kind, setKind] = useState<CreateKind>("cli");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mcpServerId, setMcpServerId] = useState(mcpServers[0]?.id ?? "");
  const [cliCommand, setCliCommand] = useState("");
  /** Discovery config snapshot kept until Create tool (CLI only). */
  const [cliConfig, setCliConfig] = useState<Record<string, unknown> | null>(
    null,
  );
  /** Discovery snapshot kept until Create tool (MCP only). */
  const [mcpDiscovery, setMcpDiscovery] =
    useState<McpDiscoverySelection | null>(null);
  const [httpMethod, setHttpMethod] = useState("POST");
  const [httpUrl, setHttpUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [createdName, setCreatedName] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const activeKind = KIND_CARDS.find((card) => card.id === kind) ?? KIND_CARDS[0];

  const readiness = useMemo(() => {
    return [
      {
        id: "org",
        label: "Organisation",
        done: showTenantPicker ? Boolean(tenantId) : true,
      },
      { id: "type", label: "Tool type", done: true },
      {
        id: "config",
        label: "Configuration",
        done:
          Boolean(name.trim()) &&
          (kind === "cli"
            ? Boolean(cliCommand.trim())
            : kind === "mcp"
              ? Boolean(mcpDiscovery || mcpServerId)
              : Boolean(httpUrl.trim())),
      },
    ];
  }, [
    showTenantPicker,
    tenantId,
    name,
    kind,
    cliCommand,
    mcpDiscovery,
    mcpServerId,
    httpUrl,
  ]);

  function onTenantChange(nextTenantId: string) {
    setTenantId(nextTenantId);
    const nextMcpServers = getMockMcpServers(nextTenantId);
    setMcpServerId(nextMcpServers[0]?.id ?? "");
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    if (showTenantPicker && !tenantId) {
      setError("Select an organisation.");
      return;
    }
    const toolName = name.trim();
    if (!toolName) {
      setError("Tool name is required.");
      return;
    }
    if (kind === "mcp" && !mcpDiscovery && !mcpServerId) {
      setError("Use a discovered MCP tool, or pick an existing MCP server.");
      return;
    }
    if (kind === "cli" && !cliCommand.trim()) {
      setError("CLI command is required.");
      return;
    }
    if (kind === "http" && !httpUrl.trim()) {
      setError("HTTP URL is required.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      if (kind === "cli" || kind === "mcp") {
        const bearer = accessToken ?? (await resolveSessionAccessToken());
        if (!bearer) {
          setError("Sign in to save tools.");
          return;
        }
        if (!effectiveTenantId) {
          setError("Organisation context is missing; cannot save the tool.");
          return;
        }

        if (kind === "cli") {
          const config = buildCliConfig(cliCommand, cliConfig);
          const saved = await apiClient.post<ToolCreateResponse>("/tools", {
            accessToken: bearer,
            clientId: effectiveTenantId,
            json: {
              name: toolName,
              kind: "cli",
              description: description.trim() || null,
              config,
            },
          });
          setCreatedName(saved?.name ?? toolName);
          return;
        }

        // kind === "mcp": register mcp_servers + tool_registry together.
        if (mcpDiscovery) {
          const transport = normalizeMcpTransport(
            mcpDiscovery.metadata.transport,
          );
          const connection_config = buildMcpConnectionConfig(mcpDiscovery);
          const toolConfig =
            mcpDiscovery.metadata &&
            typeof mcpDiscovery.metadata === "object"
              ? {
                  registry_id: mcpDiscovery.id,
                  source: mcpDiscovery.source,
                }
              : null;
          const saved = await apiClient.post<ToolCreateResponse>("/tools", {
            accessToken: bearer,
            clientId: effectiveTenantId,
            json: {
              name: toolName,
              kind: "mcp",
              description: description.trim() || null,
              config: toolConfig,
              mcp_server: {
                name: mcpDiscovery.name || toolName,
                transport,
                connection_config,
                enabled: true,
              },
            },
          });
          setCreatedName(saved?.name ?? toolName);
          return;
        }

        // Fallback: link to an already-known mock/local MCP server id.
        const saved = await apiClient.post<ToolCreateResponse>("/tools", {
          accessToken: bearer,
          clientId: effectiveTenantId,
          json: {
            name: toolName,
            kind: "mcp",
            description: description.trim() || null,
            mcp_server_id: mcpServerId,
          },
        });
        setCreatedName(saved?.name ?? toolName);
        return;
      }

      // HTTP still mock until that discovery flow saves to the API.
      if (existing.some((t) => t.name === toolName)) {
        setError(`A tool named "${toolName}" already exists.`);
        return;
      }
      const row = createMockTool({
        name: toolName,
        kind: kind as MockToolKind,
        description,
        mcpServerId: null,
        mcpServers,
        cliCommand,
        httpUrl: `${httpMethod} ${httpUrl.trim()}`,
      });
      setCreatedName(row.name);
    } catch (err) {
      setError(saveErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (createdName) {
    const tenantSuffix = selectedTenant ? ` for ${selectedTenant.name}` : "";
    return (
      <div className={styles.createShell}>
        <div className={styles.successCard}>
          <div className={`${styles.successIcon} ${KIND_TONE[kind]}`}>
            <KindIcon kind={kind} />
          </div>
          <h2 className={styles.successTitle}>Tool created</h2>
          <p className={styles.successText}>
            <strong>{createdName}</strong> ({kind.toUpperCase()}){tenantSuffix} is
            ready to use.
          </p>
          <div className={styles.successActions}>
            <button
              type="button"
              className={panel.btnPrimary}
              onClick={() => router.push(cancelHref)}
            >
              Back to tools
            </button>
            <button
              type="button"
              onClick={() => {
                setCreatedName(null);
                setName("");
                setDescription("");
                setCliCommand("");
                setCliConfig(null);
                setMcpDiscovery(null);
                setHttpUrl("");
              }}
            >
              Create another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.createShell}>
      <nav className={styles.stepRail} aria-label="Create tool progress">
        {readiness.map((step, index) => (
          <div
            key={step.id}
            className={`${styles.stepItem} ${step.done ? styles.stepDone : ""}`}
          >
            <span className={styles.stepIndex}>{index + 1}</span>
            <span className={styles.stepLabel}>{step.label}</span>
          </div>
        ))}
      </nav>

      <div className={styles.createGrid}>
        <aside className={styles.createAside}>
          <section className={styles.asideCard}>
            <p className={styles.asideEyebrow}>Selected type</p>
            <div className={styles.asideTypeRow}>
              <span className={`${styles.asideTypeIcon} ${KIND_TONE[kind]}`}>
                <KindIcon kind={kind} />
              </span>
              <div>
                <p className={styles.asideTypeTitle}>{activeKind.title}</p>
                <p className={styles.asideTypeText}>{activeKind.text}</p>
              </div>
            </div>
          </section>

          <section className={styles.asideCard}>
            <p className={styles.asideEyebrow}>Summary</p>
            <dl className={styles.summaryList}>
              <div>
                <dt>Organisation</dt>
                <dd>{selectedTenant?.name ?? "Current organisation"}</dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>{activeKind.badge}</dd>
              </div>
              <div>
                <dt>Name</dt>
                <dd>{name.trim() || "—"}</dd>
              </div>
            </dl>
          </section>
        </aside>

        <div className={styles.createMain}>
          {error ? (
            <p className={panel.error} role="alert">
              {error}
            </p>
          ) : null}

          {showTenantPicker ? (
            <section className={styles.workspaceCard}>
              <div className={styles.cardHead}>
                <div>
                  <h2 className={styles.cardTitle}>Organisation</h2>
                  <p className={styles.cardDesc}>
                    Assign this tool to a tenant before configuration.
                  </p>
                </div>
              </div>
              <label className={panel.formLabel}>
                Organisation
                <span className={panel.formHint}>Tools are registered per organisation</span>
                <select
                  value={tenantId}
                  onChange={(ev) => onTenantChange(ev.target.value)}
                  required
                >
                  {tenants?.map((tenant) => (
                    <option key={tenant.id} value={tenant.id}>
                      {tenant.name} ({tenant.slug})
                    </option>
                  ))}
                </select>
              </label>
            </section>
          ) : tenantLabel ? (
            <p className={styles.tenantChip}>
              Creating for <strong>{tenantLabel}</strong>
            </p>
          ) : null}

          <section className={styles.workspaceCard}>
            <div className={styles.cardHead}>
              <div>
                <h2 className={styles.cardTitle}>Tool type</h2>
                <p className={styles.cardDesc}>
                  Choose how the agent will invoke this capability.
                </p>
              </div>
            </div>
            <div className={styles.kindCards} role="radiogroup" aria-label="Tool type">
              {KIND_CARDS.map((card) => {
                const active = kind === card.id;
                return (
                  <button
                    key={card.id}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    className={`${styles.kindCard} ${KIND_TONE[card.id]} ${
                      active ? styles.kindCardActive : ""
                    }`}
                    onClick={() => {
                      setKind(card.id);
                      setCliConfig(null);
                      setMcpDiscovery(null);
                      setError(null);
                    }}
                  >
                    <span className={styles.kindCardIcon}>
                      <KindIcon kind={card.id} />
                    </span>
                    <span className={styles.kindCardBadge}>{card.badge}</span>
                    <p className={styles.kindCardTitle}>{card.title}</p>
                    <p className={styles.kindCardText}>{card.text}</p>
                  </button>
                );
              })}
            </div>
          </section>

          <div className={styles.detailSplit}>
            {kind === "cli" ? (
              <ToolDiscoveryPanel
                accessToken={accessToken}
                onSelect={(tool) => {
                  setName(tool.name);
                  setDescription(tool.summary);
                  const command =
                    typeof tool.config?.command === "string"
                      ? tool.config.command.trim()
                      : "";
                  setCliCommand(command || tool.name);
                  setCliConfig(
                    tool.config && typeof tool.config === "object"
                      ? { ...tool.config }
                      : null,
                  );
                  setError(null);
                }}
              />
            ) : kind === "mcp" ? (
              <McpToolDiscoveryPanel
                accessToken={accessToken}
                onSelect={(tool) => {
                  setName(tool.name);
                  setDescription(tool.summary);
                  setMcpDiscovery({
                    id: tool.id,
                    name: tool.name,
                    source: tool.source,
                    metadata:
                      tool.metadata && typeof tool.metadata === "object"
                        ? { ...tool.metadata }
                        : {},
                  });
                  const match = mcpServers.find(
                    (s) =>
                      s.name === tool.name ||
                      s.name === tool.id ||
                      tool.id.endsWith(`/${s.name}`),
                  );
                  if (match) {
                    setMcpServerId(match.id);
                  }
                  setError(null);
                }}
              />
            ) : (
              <section className={styles.workspaceCard}>
                <div className={styles.cardHead}>
                  <div>
                    <h2 className={styles.cardTitle}>Tool discovery</h2>
                    <p className={styles.cardDesc}>
                      Online discovery is available for CLI and MCP tools. Configure this{" "}
                      {kind.toUpperCase()} tool manually on the right.
                    </p>
                  </div>
                </div>
                <div className={styles.discoveryIdle}>
                  <p className={panel.meta}>
                    Switch to <strong>CLI tool</strong> or <strong>MCP tool</strong> to
                    search discovery endpoints.
                  </p>
                </div>
              </section>
            )}

            <form
              className={styles.workspaceCard}
              onSubmit={(ev) => void onSubmit(ev)}
            >
              <div className={styles.cardHead}>
                <div>
                  <h2 className={styles.cardTitle}>Configuration</h2>
                  <p className={styles.cardDesc}>
                    Define identity and runtime details for this {kind.toUpperCase()}{" "}
                    tool.
                  </p>
                </div>
              </div>

              <div className={styles.configGrid}>
                <label className={panel.formLabel}>
                  Tool name
                  <span className={panel.formHint}>Unique per organisation</span>
                  <input
                    value={name}
                    onChange={(ev) => setName(ev.target.value)}
                    required
                    placeholder={
                      kind === "cli"
                        ? "run_export"
                        : kind === "mcp"
                          ? "search_knowledge"
                          : "notify_webhook"
                    }
                  />
                </label>
                <label className={`${panel.formLabel} ${styles.configFull}`}>
                  Description
                  <textarea
                    value={description}
                    onChange={(ev) => setDescription(ev.target.value)}
                    rows={3}
                    placeholder="What the agent should use this tool for"
                  />
                </label>

                {kind === "cli" ? (
                  <label className={`${panel.formLabel} ${styles.configFull}`}>
                    CLI command
                    <span className={panel.formHint}>
                      Executed when the agent calls this tool
                    </span>
                    <input
                      value={cliCommand}
                      onChange={(ev) => setCliCommand(ev.target.value)}
                      required
                      placeholder="uv run python scripts/my_tool.py"
                      className={styles.monoInput}
                    />
                  </label>
                ) : null}

                {kind === "mcp" ? (
                  mcpDiscovery ? (
                    <div className={`${panel.formLabel} ${styles.configFull}`}>
                      <span>MCP server (from discovery)</span>
                      <span className={panel.formHint}>
                        Create registers the server and tool together
                      </span>
                      <p className={panel.meta} style={{ marginTop: "0.35rem" }}>
                        <strong>{mcpDiscovery.name}</strong>
                        {typeof mcpDiscovery.metadata.transport === "string"
                          ? ` · ${normalizeMcpTransport(mcpDiscovery.metadata.transport)}`
                          : ""}
                        {mcpDiscovery.source ? (
                          <>
                            <br />
                            <span className={styles.monoInput}>
                              {mcpDiscovery.source}
                            </span>
                          </>
                        ) : null}
                      </p>
                      <button
                        type="button"
                        className={styles.cancelLink}
                        onClick={() => setMcpDiscovery(null)}
                        style={{ marginTop: "0.5rem" }}
                      >
                        Clear discovery selection
                      </button>
                    </div>
                  ) : (
                    <label className={`${panel.formLabel} ${styles.configFull}`}>
                      MCP server
                      <span className={panel.formHint}>
                        Prefer Use from discovery, or pick an existing server
                      </span>
                      <select
                        value={mcpServerId}
                        onChange={(ev) => setMcpServerId(ev.target.value)}
                      >
                        {mcpServers.length === 0 ? (
                          <option value="">
                            No local servers — search discovery and Use a result
                          </option>
                        ) : (
                          mcpServers.map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.name} ({s.transport})
                            </option>
                          ))
                        )}
                      </select>
                    </label>
                  )
                ) : null}

                {kind === "http" ? (
                  <>
                    <label className={panel.formLabel}>
                      HTTP method
                      <select
                        value={httpMethod}
                        onChange={(ev) => setHttpMethod(ev.target.value)}
                      >
                        <option value="GET">GET</option>
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                        <option value="PATCH">PATCH</option>
                        <option value="DELETE">DELETE</option>
                      </select>
                    </label>
                    <label className={panel.formLabel}>
                      Request URL
                      <input
                        type="url"
                        value={httpUrl}
                        onChange={(ev) => setHttpUrl(ev.target.value)}
                        required
                        placeholder="https://api.example.com/tools/run"
                      />
                    </label>
                  </>
                ) : null}
              </div>

              <div className={styles.formFooter}>
                <Link href={cancelHref} className={styles.cancelLink}>
                  Cancel
                </Link>
                <button type="submit" className={panel.btnPrimary} disabled={saving}>
                  {saving ? "Saving…" : "Create tool"}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
