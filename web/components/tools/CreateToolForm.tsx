"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Globe, Server, Terminal } from "lucide-react";
import { ToolDiscoveryPanel } from "@/components/tools/ToolDiscoveryPanel";
import { McpToolDiscoveryPanel } from "@/components/tools/McpToolDiscoveryPanel";
import { ApiError, apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
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

const inputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {hint ? (
        <span className="mt-1 block text-sm text-muted-foreground">{hint}</span>
      ) : null}
      <div className="mt-2">{children}</div>
    </label>
  );
}

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
  icon: typeof Terminal;
}> = [
  {
    id: "cli",
    title: "CLI tool",
    text: "Run a shell command the agent can invoke on demand.",
    badge: "Command",
    icon: Terminal,
  },
  {
    id: "mcp",
    title: "MCP tool",
    text: "Expose a capability from a connected MCP server.",
    badge: "Protocol",
    icon: Server,
  },
  {
    id: "http",
    title: "HTTP request",
    text: "Call a REST endpoint with method, URL, and payload.",
    badge: "API",
    icon: Globe,
  },
];

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
  const [cliConfig, setCliConfig] = useState<Record<string, unknown> | null>(
    null,
  );
  const [mcpDiscovery, setMcpDiscovery] =
    useState<McpDiscoverySelection | null>(null);
  const [httpMethod, setHttpMethod] = useState("POST");
  const [httpUrl, setHttpUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [createdName, setCreatedName] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const activeKind = KIND_CARDS.find((card) => card.id === kind) ?? KIND_CARDS[0];
  const ActiveIcon = activeKind.icon;

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
      <Card>
        <CardContent className="space-y-5 py-8">
          <div className="flex items-start gap-4">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#ecfdf5] text-primary">
              <CheckCircle2 className="h-6 w-6" />
            </span>
            <div>
              <p className="text-headline-md text-foreground">Tool created</p>
              <p className="mt-2 text-body-md text-muted-foreground">
                <strong className="text-foreground">{createdName}</strong> (
                {kind.toUpperCase()}){tenantSuffix} is ready to use.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              className="rounded-full"
              onClick={() => router.push(cancelHref)}
            >
              Back to tools
            </Button>
            <Button
              type="button"
              variant="secondary"
              className="rounded-full"
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
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <nav
        aria-label="Create tool progress"
        className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-card px-5 py-4"
      >
        {readiness.map((step, index) => (
          <div key={step.id} className="flex items-center gap-2">
            <span
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold",
                step.done
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {index + 1}
            </span>
            <span
              className={cn(
                "text-sm",
                step.done
                  ? "font-medium text-foreground"
                  : "text-muted-foreground",
              )}
            >
              {step.label}
            </span>
          </div>
        ))}
      </nav>

      {error ? (
        <p
          className="rounded-lg border border-danger-muted bg-danger-muted/40 px-4 py-3 text-body-md text-danger"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      <form
        onSubmit={(ev) => void onSubmit(ev)}
        className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]"
      >
        <div className="space-y-6">
          {showTenantPicker ? (
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle className="text-headline-md">Organisation</CardTitle>
                <CardDescription>
                  Assign this tool to a tenant before configuration.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-6">
                <FormField
                  label="Organisation"
                  hint="Tools are registered per organisation"
                >
                  <select
                    value={tenantId}
                    onChange={(ev) => onTenantChange(ev.target.value)}
                    required
                    className={inputClassName}
                  >
                    {tenants?.map((tenant) => (
                      <option key={tenant.id} value={tenant.id}>
                        {tenant.name} ({tenant.slug})
                      </option>
                    ))}
                  </select>
                </FormField>
              </CardContent>
            </Card>
          ) : tenantLabel ? (
            <Card>
              <CardContent className="py-5 text-body-md text-muted-foreground">
                Creating for{" "}
                <strong className="text-foreground">{tenantLabel}</strong>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">Tool type</CardTitle>
              <CardDescription>
                Choose how the agent will invoke this capability.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <div
                role="radiogroup"
                aria-label="Tool type"
                className="grid gap-3 sm:grid-cols-3"
              >
                {KIND_CARDS.map((card) => {
                  const active = kind === card.id;
                  const Icon = card.icon;
                  return (
                    <button
                      key={card.id}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => {
                        setKind(card.id);
                        setCliConfig(null);
                        setMcpDiscovery(null);
                        setError(null);
                      }}
                      className={cn(
                        "rounded-xl border p-4 text-left transition-colors",
                        active
                          ? "border-primary bg-[#ecfdf5] ring-2 ring-primary/20"
                          : "border-border bg-card hover:bg-muted/40",
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span
                          className={cn(
                            "flex h-9 w-9 items-center justify-center rounded-lg",
                            active
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground",
                          )}
                        >
                          <Icon className="h-4 w-4" />
                        </span>
                        <Badge variant={active ? "default" : "muted"}>
                          {card.badge}
                        </Badge>
                      </div>
                      <p className="mt-3 text-sm font-semibold text-foreground">
                        {card.title}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {card.text}
                      </p>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>

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
            <Card>
              <CardHeader className="border-b border-border">
                <CardTitle className="text-headline-md">Tool discovery</CardTitle>
                <CardDescription>
                  Online discovery is available for CLI and MCP tools. Configure
                  this HTTP tool manually below.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-6 text-body-md text-muted-foreground">
                Switch to <strong className="text-foreground">CLI tool</strong> or{" "}
                <strong className="text-foreground">MCP tool</strong> to search
                discovery endpoints.
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">Configuration</CardTitle>
              <CardDescription>
                Define identity and runtime details for this{" "}
                {kind.toUpperCase()} tool.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5 pt-6">
              <FormField label="Tool name" hint="Unique per organisation">
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
                  className={inputClassName}
                />
              </FormField>

              <FormField label="Description">
                <textarea
                  value={description}
                  onChange={(ev) => setDescription(ev.target.value)}
                  rows={3}
                  placeholder="What the agent should use this tool for"
                  className={cn(inputClassName, "min-h-[5.5rem] resize-y")}
                />
              </FormField>

              {kind === "cli" ? (
                <FormField
                  label="CLI command"
                  hint="Executed when the agent calls this tool"
                >
                  <input
                    value={cliCommand}
                    onChange={(ev) => setCliCommand(ev.target.value)}
                    required
                    placeholder="uv run python scripts/my_tool.py"
                    className={cn(inputClassName, "font-mono text-[13px]")}
                  />
                </FormField>
              ) : null}

              {kind === "mcp" ? (
                mcpDiscovery ? (
                  <div className="rounded-lg border border-border bg-[#f8fafc] p-4">
                    <p className="text-sm font-medium text-foreground">
                      MCP server (from discovery)
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Create registers the server and tool together.
                    </p>
                    <p className="mt-3 text-sm text-foreground">
                      <strong>{mcpDiscovery.name}</strong>
                      {typeof mcpDiscovery.metadata.transport === "string"
                        ? ` · ${normalizeMcpTransport(mcpDiscovery.metadata.transport)}`
                        : ""}
                      {mcpDiscovery.source ? (
                        <>
                          <br />
                          <span className="text-muted-foreground">
                            {mcpDiscovery.source}
                          </span>
                        </>
                      ) : null}
                    </p>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="mt-3"
                      onClick={() => setMcpDiscovery(null)}
                    >
                      Clear discovery selection
                    </Button>
                  </div>
                ) : (
                  <FormField
                    label="MCP server"
                    hint="Prefer Use from discovery, or pick an existing server"
                  >
                    <select
                      value={mcpServerId}
                      onChange={(ev) => setMcpServerId(ev.target.value)}
                      className={inputClassName}
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
                  </FormField>
                )
              ) : null}

              {kind === "http" ? (
                <>
                  <FormField label="HTTP method">
                    <select
                      value={httpMethod}
                      onChange={(ev) => setHttpMethod(ev.target.value)}
                      className={inputClassName}
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                      <option value="PUT">PUT</option>
                      <option value="PATCH">PATCH</option>
                      <option value="DELETE">DELETE</option>
                    </select>
                  </FormField>
                  <FormField label="Request URL">
                    <input
                      type="url"
                      value={httpUrl}
                      onChange={(ev) => setHttpUrl(ev.target.value)}
                      required
                      placeholder="https://api.example.com/tools/run"
                      className={cn(inputClassName, "font-mono text-[13px]")}
                    />
                  </FormField>
                </>
              ) : null}

              <div className="flex flex-wrap gap-2 border-t border-border pt-5">
                <Button type="submit" className="rounded-full" disabled={saving}>
                  {saving ? "Saving…" : "Create tool"}
                </Button>
                <Link
                  href={cancelHref}
                  className={buttonVariants({ variant: "secondary" })}
                >
                  Cancel
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">Selected type</CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                  <ActiveIcon className="h-5 w-5" />
                </span>
                <div>
                  <p className="font-medium text-foreground">{activeKind.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {activeKind.text}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-6 text-sm">
              <div className="flex flex-col gap-1 border-b border-border pb-3">
                <span className="text-muted-foreground">Organisation</span>
                <span className="font-medium text-foreground">
                  {selectedTenant?.name ?? "Current organisation"}
                </span>
              </div>
              <div className="flex flex-col gap-1 border-b border-border pb-3">
                <span className="text-muted-foreground">Type</span>
                <span className="font-medium text-foreground">
                  {activeKind.badge}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-muted-foreground">Name</span>
                <span className="font-medium text-foreground">
                  {name.trim() || "—"}
                </span>
              </div>
            </CardContent>
          </Card>
        </aside>
      </form>
    </div>
  );
}
