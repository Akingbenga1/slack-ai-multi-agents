"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Globe, Terminal } from "lucide-react";
import { ToolDiscoveryPanel } from "@/components/tools/ToolDiscoveryPanel";
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
  type MockToolKind,
} from "@/lib/mock/tools-data";

type CreateKind = "cli" | "http";

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

  const [kind, setKind] = useState<CreateKind>("cli");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [cliCommand, setCliCommand] = useState("");
  const [cliConfig, setCliConfig] = useState<Record<string, unknown> | null>(
    null,
  );
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
            : Boolean(httpUrl.trim())),
      },
    ];
  }, [showTenantPicker, tenantId, name, kind, cliCommand, httpUrl]);

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
      if (kind === "cli") {
        const bearer = accessToken ?? (await resolveSessionAccessToken());
        if (!bearer) {
          setError("Sign in to save tools.");
          return;
        }
        if (!effectiveTenantId) {
          setError("Organisation context is missing; cannot save the tool.");
          return;
        }
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

      // HTTP tools are not on the live /tools API yet — local preview only.
      const row = createMockTool({
        name: toolName,
        kind: kind as MockToolKind,
        description,
        mcpServerId: null,
        mcpServers: [],
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
    return (
      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 text-success" />
            <div>
              <CardTitle className="text-headline-md">Tool registered</CardTitle>
              <CardDescription className="mt-1">
                <strong className="text-foreground">{createdName}</strong> is ready
                {selectedTenant?.name ? ` for ${selectedTenant.name}` : ""}.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3 pt-6">
          <Button type="button" onClick={() => router.push(cancelHref)}>
            Back to tools
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setCreatedName(null);
              setName("");
              setDescription("");
              setCliCommand("");
              setCliConfig(null);
              setHttpUrl("");
              setError(null);
            }}
          >
            Create another
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <form onSubmit={(ev) => void onSubmit(ev)} className="space-y-6">
      <Card>
        <CardHeader className="border-b border-border">
          <CardTitle className="text-headline-md">New tool</CardTitle>
          <CardDescription className="mt-1">
            Register a CLI or HTTP tool. Install MCP servers from the Tools page
            (named connection + Available), not here.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 pt-6">
          {showTenantPicker ? (
            <FormField label="Organisation">
              <select
                value={tenantId}
                onChange={(ev) => setTenantId(ev.target.value)}
                className={inputClassName}
              >
                {tenants?.map((tenant) => (
                  <option key={tenant.id} value={tenant.id}>
                    {tenant.name}
                  </option>
                ))}
              </select>
            </FormField>
          ) : selectedTenant?.name ? (
            <p className="text-body-md text-muted-foreground">
              Organisation:{" "}
              <strong className="text-foreground">{selectedTenant.name}</strong>
            </p>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2">
            {KIND_CARDS.map((card) => {
              const Icon = card.icon;
              const selected = kind === card.id;
              return (
                <button
                  key={card.id}
                  type="button"
                  onClick={() => {
                    setKind(card.id);
                    setError(null);
                  }}
                  className={cn(
                    "rounded-lg border px-4 py-4 text-left transition",
                    selected
                      ? "border-primary bg-primary/5"
                      : "border-border bg-card hover:border-primary/40",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                      <Icon className="h-4 w-4" />
                    </div>
                    <Badge variant={selected ? "default" : "muted"}>
                      {card.badge}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm font-medium text-foreground">
                    {card.title}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">{card.text}</p>
                </button>
              );
            })}
          </div>

          <ul className="flex flex-wrap gap-3 text-sm text-muted-foreground">
            {readiness.map((item) => (
              <li key={item.id} className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "inline-block h-2 w-2 rounded-full",
                    item.done ? "bg-success" : "bg-border",
                  )}
                />
                {item.label}
              </li>
            ))}
          </ul>
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
      ) : (
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle className="text-headline-md">Tool discovery</CardTitle>
            <CardDescription>
              Online discovery is available for CLI tools. Configure this HTTP
              tool manually below.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
              <ActiveIcon className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-headline-md">Configuration</CardTitle>
              <CardDescription>
                Define identity and runtime details for this{" "}
                {kind.toUpperCase()} tool.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 pt-6">
          <FormField label="Tool name" hint="Unique per organisation">
            <input
              value={name}
              onChange={(ev) => setName(ev.target.value)}
              required
              placeholder={kind === "cli" ? "run_export" : "notify_webhook"}
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
              hint="Executable or entrypoint the agent will run"
            >
              <input
                value={cliCommand}
                onChange={(ev) => setCliCommand(ev.target.value)}
                required
                placeholder="jq"
                className={inputClassName}
              />
            </FormField>
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
                  placeholder="https://api.example.com/hooks"
                  className={inputClassName}
                />
              </FormField>
            </>
          ) : null}

          {error ? (
            <p className="rounded-lg border border-danger/20 bg-danger-muted px-4 py-3 text-body-md text-danger">
              {error}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save tool"}
            </Button>
            <Link
              href={cancelHref}
              className={cn(buttonVariants({ variant: "secondary" }))}
            >
              Cancel
            </Link>
          </div>
        </CardContent>
      </Card>
    </form>
  );
}
