"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw, Server, Trash2 } from "lucide-react";
import {
  checkMcpServer,
  createMcpServer,
  deleteMcpServer,
  listMcpServers,
  mcpApiErrorMessage,
  readinessLabel,
  startMcpOAuth,
  updateMcpServer,
  type McpServerRecord,
} from "@/lib/mcp-servers";
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

const inputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

export function TenantMcpServersPanel({ accessToken, tenantId }: Props) {
  const [servers, setServers] = useState<McpServerRecord[] | null | undefined>(
    undefined,
  );
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [rowBusy, setRowBusy] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [serviceToken, setServiceToken] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [verifyOnSave, setVerifyOnSave] = useState(true);

  const reload = useCallback(async () => {
    if (!accessToken) {
      setServers(null);
      setError(null);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const rows = await listMcpServers(accessToken, tenantId);
      setServers(rows);
    } catch (err) {
      setServers(null);
      setError(mcpApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }, [accessToken, tenantId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  function resetForm() {
    setName("");
    setUrl("");
    setServiceToken("");
    setEnabled(true);
    setVerifyOnSave(true);
    setShowForm(false);
  }

  async function onCreate(ev: FormEvent) {
    ev.preventDefault();
    if (!accessToken) return;
    const cleanName = name.trim();
    const cleanUrl = url.trim();
    if (!cleanName || !cleanUrl) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const row = await createMcpServer(accessToken, tenantId, {
        name: cleanName,
        url: cleanUrl,
        service_token: serviceToken.trim() || null,
        enabled,
        verify: verifyOnSave,
      });
      setServers((prev) => {
        const rest = (prev || []).filter((s) => s.id !== row.id);
        return [row, ...rest].sort((a, b) =>
          a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
        );
      });
      const readyNote =
        row.readiness?.ready === true
          ? " Ready."
          : row.readiness?.error
            ? ` Saved; readiness: ${row.readiness.error}`
            : verifyOnSave
              ? " Saved."
              : " Saved without verify.";
      setMessage(`Added MCP server "${row.name}".${readyNote}`);
      resetForm();
    } catch (err) {
      setError(mcpApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function onToggleAvailable(server: McpServerRecord) {
    if (!accessToken) return;
    setRowBusy(server.id);
    setError(null);
    setMessage(null);
    try {
      const row = await updateMcpServer(accessToken, tenantId, server.id, {
        enabled: !server.enabled,
        verify: false,
      });
      setServers((prev) =>
        (prev || []).map((s) => (s.id === row.id ? { ...s, ...row } : s)),
      );
      setMessage(
        row.enabled
          ? `"${row.name}" is available on the tenant profile.`
          : `"${row.name}" is not available for Deep Agents.`,
      );
    } catch (err) {
      setError(mcpApiErrorMessage(err));
    } finally {
      setRowBusy(null);
    }
  }

  async function onConnect(server: McpServerRecord) {
    if (!accessToken) return;
    setRowBusy(server.id);
    setError(null);
    setMessage(null);
    try {
      const started = await startMcpOAuth(accessToken, tenantId, server.id);
      window.open(started.authorization_url, "_blank", "noopener,noreferrer");
      setMessage(
        `Connect started for "${server.name}". Complete sign-in in the new window, then Refresh.`,
      );
    } catch (err) {
      setError(mcpApiErrorMessage(err));
    } finally {
      setRowBusy(null);
    }
  }

  async function onCheck(server: McpServerRecord) {
    if (!accessToken) return;
    setRowBusy(server.id);
    setError(null);
    setMessage(null);
    try {
      const row = await checkMcpServer(accessToken, tenantId, server.id);
      setServers((prev) =>
        (prev || []).map((s) => (s.id === row.id ? { ...s, ...row } : s)),
      );
      setMessage(`Checked "${row.name}": ${readinessLabel(row)}`);
    } catch (err) {
      setError(mcpApiErrorMessage(err));
    } finally {
      setRowBusy(null);
    }
  }

  async function onRemove(server: McpServerRecord) {
    if (!accessToken) return;
    if (!window.confirm(`Remove MCP server "${server.name}"?`)) return;
    setRowBusy(server.id);
    setError(null);
    setMessage(null);
    try {
      await deleteMcpServer(accessToken, tenantId, server.id);
      setServers((prev) => (prev || []).filter((s) => s.id !== server.id));
      setMessage(`Removed MCP server "${server.name}".`);
    } catch (err) {
      setError(mcpApiErrorMessage(err));
    } finally {
      setRowBusy(null);
    }
  }

  if (!accessToken) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-headline-md">MCP servers</CardTitle>
          <CardDescription>
            Sign in to manage remote MCP servers for your organisation.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const list = servers ?? [];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle className="text-headline-md">MCP servers</CardTitle>
              <CardDescription className="mt-1">
                Named remote connections (display name + URL). Optional Bearer
                service token for authenticated remotes. Select Available so
                Deep Agents may use them when relevant. Connect/OAuth comes
                next.
              </CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="secondary"
                className="rounded-full"
                disabled={busy}
                onClick={() => void reload()}
              >
                <RefreshCw className={cn("h-4 w-4", busy && "animate-spin")} />
                Refresh
              </Button>
              <Button
                type="button"
                className="rounded-full"
                onClick={() => setShowForm((open) => !open)}
              >
                <Plus className="h-4 w-4" />
                {showForm ? "Cancel" : "Add MCP server"}
              </Button>
            </div>
          </div>
        </CardHeader>
        {message ? (
          <CardContent className="border-b border-border pt-6">
            <p
              className="rounded-lg border border-success/20 bg-success-muted px-4 py-3 text-body-md text-success"
              role="status"
            >
              {message}
            </p>
          </CardContent>
        ) : null}
        {error ? (
          <CardContent className="border-b border-border pt-6">
            <p
              className="rounded-lg border border-danger/20 bg-danger-muted px-4 py-3 text-body-md text-danger"
              role="alert"
            >
              {error}
            </p>
          </CardContent>
        ) : null}
      </Card>

      {showForm ? (
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle className="text-headline-md">New MCP server</CardTitle>
            <CardDescription>
              Unauthenticated: name + URL. Authenticated: add optional service
              token (stored encrypted, never shown again).
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form onSubmit={(ev) => void onCreate(ev)} className="grid max-w-2xl gap-4">
              <label className="block">
                <span className="text-sm font-medium text-foreground">
                  Display name
                </span>
                <span className="mt-1 block text-sm text-muted-foreground">
                  Unique per organisation — letters, numbers, _ and -
                </span>
                <input
                  value={name}
                  onChange={(ev) => setName(ev.target.value)}
                  required
                  pattern="[A-Za-z0-9_-]+"
                  className={cn(inputClassName, "mt-2")}
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-foreground">
                  Remote URL
                </span>
                <input
                  type="url"
                  value={url}
                  onChange={(ev) => setUrl(ev.target.value)}
                  placeholder="https://mcp.example.com/mcp"
                  required
                  className={cn(inputClassName, "mt-2 font-mono text-[13px]")}
                />
              </label>
              <label className="block">
                <span className="text-sm font-medium text-foreground">
                  Service token (optional)
                </span>
                <span className="mt-1 block text-sm text-muted-foreground">
                  Bearer credential for token-style remotes. Leave blank for
                  unauthenticated servers.
                </span>
                <input
                  type="password"
                  value={serviceToken}
                  onChange={(ev) => setServiceToken(ev.target.value)}
                  autoComplete="off"
                  className={cn(inputClassName, "mt-2 font-mono text-[13px]")}
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(ev) => setEnabled(ev.target.checked)}
                  className="h-4 w-4 rounded border-border"
                />
                Available on tenant profile for Deep Agents
              </label>
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={verifyOnSave}
                  onChange={(ev) => setVerifyOnSave(ev.target.checked)}
                  className="h-4 w-4 rounded border-border"
                />
                Verify readiness on save
              </label>
              <div className="flex flex-wrap gap-2">
                <Button type="submit" className="rounded-full" disabled={busy}>
                  <Server className="h-4 w-4" />
                  Save MCP server
                </Button>
                <Button type="button" variant="ghost" onClick={resetForm}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-6 py-5">
          <div>
            <h2 className="text-headline-md text-foreground">Installed servers</h2>
            <p className="mt-1 text-body-md text-muted-foreground">
              {servers === undefined
                ? "Loading…"
                : `${list.length} remote MCP connection(s).`}
            </p>
          </div>
          {list.length > 0 ? <Badge variant="muted">{list.length}</Badge> : null}
        </div>
        <CardContent className="px-0 pb-0 pt-0">
          {servers === undefined ? (
            <p className="px-6 py-8 text-center text-body-md text-muted-foreground">
              Loading MCP servers…
            </p>
          ) : list.length === 0 ? (
            <p className="px-6 py-8 text-center text-body-md text-muted-foreground">
              No MCP servers yet — add a named remote URL for your organisation.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[880px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border bg-[#f8fafc]">
                    <th className="px-6 py-3 text-label-md text-muted-foreground">
                      Name
                    </th>
                    <th className="px-4 py-3 text-label-md text-muted-foreground">
                      URL
                    </th>
                    <th className="px-4 py-3 text-label-md text-muted-foreground">
                      Credential
                    </th>
                    <th className="px-4 py-3 text-label-md text-muted-foreground">
                      Available
                    </th>
                    <th className="px-4 py-3 text-label-md text-muted-foreground">
                      Readiness
                    </th>
                    <th className="px-6 py-3 text-right text-label-md text-muted-foreground">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((server) => {
                    const rowLoading = rowBusy === server.id;
                    return (
                      <tr
                        key={server.id}
                        className="border-b border-border last:border-b-0 hover:bg-muted/40"
                      >
                        <td className="px-6 py-3">
                          <p className="font-medium text-foreground">
                            {server.name}
                          </p>
                          <code className="mt-1 block text-xs text-muted-foreground">
                            {server.transport}
                          </code>
                        </td>
                        <td className="px-4 py-3">
                          <code className="break-all text-xs text-foreground">
                            {server.url || "—"}
                          </code>
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={
                              server.has_oauth_credential
                                ? "success"
                                : server.has_service_credential
                                  ? "warning"
                                  : "muted"
                            }
                          >
                            {server.has_oauth_credential
                              ? "OAuth connected"
                              : server.has_service_credential
                                ? "Bearer stored"
                                : "None"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={server.enabled ? "success" : "muted"}>
                            {server.enabled ? "Available" : "Not available"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {readinessLabel(server)}
                        </td>
                        <td className="px-6 py-3 text-right">
                          <div className="flex flex-wrap justify-end gap-1">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              disabled={rowLoading}
                              onClick={() => void onConnect(server)}
                            >
                              Connect
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              disabled={rowLoading}
                              onClick={() => void onToggleAvailable(server)}
                            >
                              {server.enabled ? "Make unavailable" : "Make available"}
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              disabled={rowLoading}
                              onClick={() => void onCheck(server)}
                            >
                              Check
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              disabled={rowLoading}
                              onClick={() => void onRemove(server)}
                              className="text-danger hover:text-danger"
                            >
                              <Trash2 className="h-4 w-4" />
                              Remove
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
