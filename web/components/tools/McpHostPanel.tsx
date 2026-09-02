"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Server } from "lucide-react";
import { ApiError, apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
};

type McpHostServer = {
  id: string;
  name: string;
  transport: string;
  enabled: boolean;
  endpoint_hint?: string | null;
  linked_tools: string[];
  created_at?: string | null;
};

type McpHostListResponse = {
  servers: McpHostServer[];
  bundled: McpHostServer;
  check_timeout_seconds: number;
};

type HostStatus = {
  ready: boolean | null;
  busy?: "check" | "toggle" | null;
  message?: string | null;
  detail?: string | null;
  toolCount?: number | null;
};

function errMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Sign in to manage MCP host readiness.";
    if (err.status === 403) return err.message || "Not allowed.";
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

function readinessVariant(
  st: HostStatus | undefined,
  server: McpHostServer,
): "success" | "warning" | "danger" | "muted" {
  if (st?.busy) return "muted";
  if (st?.ready === true) return "success";
  if (st?.ready === false && server.enabled) return "danger";
  if (!server.enabled && server.id !== "__bundled__") return "muted";
  if (st?.message) return "danger";
  return "muted";
}

export function McpHostPanel({ accessToken, tenantId }: Props) {
  const [servers, setServers] = useState<McpHostServer[] | null | undefined>(undefined);
  const [bundled, setBundled] = useState<McpHostServer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [statusByName, setStatusByName] = useState<Record<string, HostStatus>>({});
  const [checkingAll, setCheckingAll] = useState(false);

  const patchStatus = useCallback((name: string, patch: Partial<HostStatus>) => {
    setStatusByName((prev) => ({
      ...prev,
      [name]: { ...prev[name], ready: prev[name]?.ready ?? null, ...patch },
    }));
  }, []);

  const checkOne = useCallback(
    async (server: McpHostServer) => {
      if (!accessToken) return;
      const path =
        server.id === "__bundled__"
          ? "/mcp-host/bundled/check"
          : `/mcp-host/${encodeURIComponent(server.name)}/check`;
      patchStatus(server.name, { busy: "check", message: null, detail: null });
      try {
        const body = await apiClient.post<{
          ready: boolean;
          error?: string | null;
          detail?: string | null;
          tool_count?: number | null;
        }>(path, { accessToken, clientId: tenantId });
        patchStatus(server.name, {
          busy: null,
          ready: Boolean(body?.ready),
          message: body?.ready ? null : body?.error || "Not ready",
          detail: body?.detail ?? null,
          toolCount: body?.tool_count ?? null,
        });
      } catch (err) {
        patchStatus(server.name, {
          busy: null,
          ready: null,
          message: errMessage(err),
          detail: null,
        });
      }
    },
    [accessToken, tenantId, patchStatus],
  );

  const checkAll = useCallback(
    async (list: McpHostServer[]) => {
      if (!accessToken || list.length === 0) return;
      setCheckingAll(true);
      try {
        await Promise.all(list.map((server) => checkOne(server)));
      } finally {
        setCheckingAll(false);
      }
    },
    [accessToken, checkOne],
  );

  const load = useCallback(async () => {
    if (!accessToken) {
      setServers(null);
      setBundled(null);
      return;
    }
    const body = await apiClient.get<McpHostListResponse>("/mcp-host", {
      accessToken,
      clientId: tenantId,
    });
    const rows = body?.servers ?? [];
    const bundledRow = body?.bundled ?? null;
    setServers(rows);
    setBundled(bundledRow);
    void checkAll(bundledRow ? [bundledRow, ...rows] : rows);
  }, [accessToken, tenantId, checkAll]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setError(null);
        await load();
      } catch (err) {
        if (!cancelled) setError(errMessage(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  async function onToggleEnabled(server: McpHostServer) {
    if (!accessToken || server.id === "__bundled__") return;
    patchStatus(server.name, { busy: "toggle", message: null });
    try {
      const updated = await apiClient.patch<McpHostServer>(
        `/mcp-host/${encodeURIComponent(server.name)}`,
        {
          accessToken,
          clientId: tenantId,
          json: { enabled: !server.enabled },
        },
      );
      if (!updated) {
        patchStatus(server.name, { busy: null });
        return;
      }
      setServers((prev) =>
        (prev ?? []).map((row) => (row.name === server.name ? { ...row, ...updated } : row)),
      );
      setNote(
        updated.enabled ? `Enabled “${server.name}”.` : `Disabled “${server.name}”.`,
      );
      patchStatus(server.name, { busy: null });
      await checkOne({ ...server, enabled: Boolean(updated.enabled) });
    } catch (err) {
      patchStatus(server.name, { busy: null, message: errMessage(err) });
    }
  }

  if (!accessToken) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-body-md text-muted-foreground">
          Sign in to check MCP server readiness.
        </CardContent>
      </Card>
    );
  }

  if (servers === undefined) {
    return (
      <Card>
        <CardContent className="space-y-2 py-8">
          {Array.from({ length: 4 }, (_, key) => (
            <div key={key} className="h-10 animate-pulse rounded-lg bg-muted" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <p className="rounded-lg border border-danger-muted bg-danger-muted/40 px-4 py-3 text-body-md text-danger" role="alert">
        {error}
      </p>
    );
  }

  const rows = bundled ? [bundled, ...(servers ?? [])] : (servers ?? []);

  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-body-md text-muted-foreground">
          No MCP servers registered yet. Create an MCP tool under Tools, then return here to verify
          the server is reachable.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                <Server className="h-5 w-5" />
              </span>
              <div>
                <CardTitle className="text-headline-md">MCP servers</CardTitle>
                <CardDescription className="mt-1">
                  {servers?.length ?? 0} registered server(s)
                  {checkingAll ? " · checking…" : ""}. Ready means this host can initialize the
                  MCP session and list tools.
                </CardDescription>
              </div>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="rounded-full"
              disabled={checkingAll}
              onClick={() => {
                setNote(null);
                void load();
              }}
            >
              <RefreshCw className={cn("h-4 w-4", checkingAll && "animate-spin")} />
              {checkingAll ? "Checking…" : "Refresh"}
            </Button>
          </div>
        </CardHeader>
        {note ? (
          <CardContent className="border-b border-border pt-6">
            <p
              className="rounded-lg border border-success/20 bg-success-muted px-4 py-3 text-body-md text-success"
              role="status"
            >
              {note}
            </p>
          </CardContent>
        ) : null}
        <CardContent className="px-0 pb-0 pt-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-[#f8fafc]">
                  <th scope="col" className="px-6 py-3 text-label-md text-muted-foreground">
                    Server
                  </th>
                  <th scope="col" className="px-4 py-3 text-label-md text-muted-foreground">
                    Transport
                  </th>
                  <th scope="col" className="px-4 py-3 text-label-md text-muted-foreground">
                    Status
                  </th>
                  <th scope="col" className="px-6 py-3 text-right text-label-md text-muted-foreground">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((server) => {
                  const st = statusByName[server.name];
                  const busy = st?.busy;
                  let statusLabel = "Checking…";
                  if (busy === "check") statusLabel = "Checking…";
                  else if (busy === "toggle") statusLabel = "Updating…";
                  else if (st?.ready === true) {
                    statusLabel =
                      typeof st.toolCount === "number"
                        ? `Ready · ${st.toolCount} tool(s)`
                        : "Ready";
                  } else if (st?.ready === false) {
                    statusLabel = server.enabled ? "Not ready" : "Disabled";
                  } else if (st?.message) {
                    statusLabel = "Check failed";
                  }
                  return (
                    <tr
                      key={server.id}
                      className="border-b border-border last:border-b-0 align-top hover:bg-muted/40"
                    >
                      <td className="px-6 py-3">
                        <p className="font-medium text-foreground">{server.name}</p>
                        {server.endpoint_hint ? (
                          <code className="mt-1 block text-xs text-muted-foreground">
                            {server.endpoint_hint}
                          </code>
                        ) : (
                          <p className="mt-1 text-xs text-muted-foreground">
                            No endpoint in connection config
                          </p>
                        )}
                        {server.linked_tools.length > 0 ? (
                          <p className="mt-1 text-xs text-muted-foreground">
                            Tools: {server.linked_tools.join(", ")}
                          </p>
                        ) : server.id === "__bundled__" ? (
                          <p className="mt-1 text-xs text-muted-foreground">Platform bundled MCP</p>
                        ) : (
                          <p className="mt-1 text-xs text-muted-foreground">
                            No linked registry tools
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <code className="text-xs uppercase text-foreground">{server.transport}</code>
                        {!server.enabled && server.id !== "__bundled__" ? (
                          <p className="mt-1 text-xs text-muted-foreground">disabled</p>
                        ) : null}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={readinessVariant(st, server)}>{statusLabel}</Badge>
                        {st?.message && st.ready !== true ? (
                          <p className="mt-2 text-xs text-danger">{st.message}</p>
                        ) : null}
                        {st?.detail && st.ready !== true ? (
                          <p className="mt-1 text-xs text-muted-foreground">{st.detail}</p>
                        ) : null}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={Boolean(busy)}
                            onClick={() => void checkOne(server)}
                          >
                            {busy === "check" ? "Checking…" : "Check"}
                          </Button>
                          {server.id !== "__bundled__" ? (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              disabled={Boolean(busy)}
                              onClick={() => void onToggleEnabled(server)}
                            >
                              {busy === "toggle"
                                ? "Updating…"
                                : server.enabled
                                  ? "Disable"
                                  : "Enable"}
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
