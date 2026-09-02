"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Terminal } from "lucide-react";
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

type CliHostTool = {
  id: string;
  name: string;
  description?: string | null;
  command?: string | null;
  package?: string | null;
  install?: string | null;
  has_install_spec: boolean;
  created_at?: string | null;
};

type CliHostListResponse = {
  tools: CliHostTool[];
  platform: string;
  install_enabled: boolean;
};

type HostStatus = {
  installed: boolean | null;
  busy?: "check" | "install" | "save" | "delete" | null;
  message?: string | null;
};

type SpecDraft = {
  package: string;
  install: string;
};

const inputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

function errMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Sign in to manage host CLI tools.";
    if (err.status === 403) return err.message || "Install is disabled on this host.";
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

function draftFromTool(tool: CliHostTool): SpecDraft {
  return {
    package: tool.package ?? "",
    install: tool.install ?? "",
  };
}

function installVariant(
  st: HostStatus | undefined,
): "success" | "warning" | "danger" | "muted" {
  if (st?.busy) return "muted";
  if (st?.installed === true) return "success";
  if (st?.installed === false) return "warning";
  if (st?.message) return "danger";
  return "muted";
}

export function CliHostPanel({ accessToken, tenantId }: Props) {
  const [tools, setTools] = useState<CliHostTool[] | null | undefined>(undefined);
  const [platform, setPlatform] = useState("");
  const [installEnabled, setInstallEnabled] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [statusByName, setStatusByName] = useState<Record<string, HostStatus>>({});
  const [checkingAll, setCheckingAll] = useState(false);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [draftByName, setDraftByName] = useState<Record<string, SpecDraft>>({});

  const patchStatus = useCallback((name: string, patch: Partial<HostStatus>) => {
    setStatusByName((prev) => ({
      ...prev,
      [name]: { ...prev[name], installed: prev[name]?.installed ?? null, ...patch },
    }));
  }, []);

  const checkOne = useCallback(
    async (tool: CliHostTool) => {
      if (!accessToken) return;
      patchStatus(tool.name, { busy: "check", message: null });
      try {
        const body = await apiClient.post<{ installed: boolean }>(
          `/cli-host/${encodeURIComponent(tool.name)}/check`,
          { accessToken, clientId: tenantId },
        );
        patchStatus(tool.name, {
          busy: null,
          installed: Boolean(body?.installed),
          message: null,
        });
      } catch (err) {
        patchStatus(tool.name, {
          busy: null,
          installed: null,
          message: errMessage(err),
        });
      }
    },
    [accessToken, tenantId, patchStatus],
  );

  const checkAll = useCallback(
    async (list: CliHostTool[]) => {
      if (!accessToken || list.length === 0) return;
      setCheckingAll(true);
      try {
        await Promise.all(list.map((tool) => checkOne(tool)));
      } finally {
        setCheckingAll(false);
      }
    },
    [accessToken, checkOne],
  );

  const load = useCallback(async () => {
    if (!accessToken) {
      setTools(null);
      return;
    }
    const body = await apiClient.get<CliHostListResponse>("/cli-host", {
      accessToken,
      clientId: tenantId,
    });
    const list = body?.tools ?? [];
    setTools(list);
    setPlatform(body?.platform ?? "");
    setInstallEnabled(body?.install_enabled ?? false);
    setStatusByName({});
    setEditingName(null);
    setDraftByName({});
    await checkAll(list);
  }, [accessToken, tenantId, checkAll]);

  useEffect(() => {
    let cancelled = false;
    setTools(undefined);
    setError(null);
    setNote(null);
    load().catch((err) => {
      if (!cancelled) {
        setTools(null);
        setError(errMessage(err));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  function openSpecEditor(tool: CliHostTool) {
    setDraftByName((prev) => ({ ...prev, [tool.name]: draftFromTool(tool) }));
    setEditingName(tool.name);
    setNote(null);
  }

  function closeSpecEditor() {
    setEditingName(null);
  }

  async function saveSpec(tool: CliHostTool, options?: { clear?: boolean }) {
    if (!accessToken) return;
    const clear = Boolean(options?.clear);
    const draft = clear
      ? { package: "", install: "" }
      : (draftByName[tool.name] ?? draftFromTool(tool));
    setNote(null);
    patchStatus(tool.name, { busy: "save", message: null });
    try {
      const updated = await apiClient.patch<CliHostTool>(
        `/cli-host/${encodeURIComponent(tool.name)}/install-spec`,
        {
          accessToken,
          clientId: tenantId,
          json: {
            package: draft.package,
            install: draft.install,
          },
        },
      );
      if (updated) {
        setTools((prev) =>
          (prev ?? []).map((row) => (row.name === tool.name ? { ...row, ...updated } : row)),
        );
        setDraftByName((prev) => ({ ...prev, [tool.name]: draftFromTool(updated) }));
      }
      patchStatus(tool.name, { busy: null, message: null });
      setNote(
        clear
          ? `Cleared install spec for “${tool.name}”.`
          : `Saved install spec for “${tool.name}”.`,
      );
      if (clear) setEditingName(null);
    } catch (err) {
      patchStatus(tool.name, {
        busy: null,
        message: errMessage(err),
      });
    }
  }

  async function onInstall(tool: CliHostTool) {
    if (!accessToken) return;
    if (!installEnabled) {
      setNote("Host install is disabled (CLI_HOST_INSTALL_ENABLED=false).");
      return;
    }
    setNote(null);
    patchStatus(tool.name, { busy: "install", message: null });
    try {
      const body = await apiClient.post<{
        ok: boolean;
        installed: boolean;
        error?: string | null;
        exit_code?: number | null;
      }>(`/cli-host/${encodeURIComponent(tool.name)}/install`, {
        accessToken,
        clientId: tenantId,
      });
      const installed = Boolean(body?.installed);
      const failMsg =
        body?.error ||
        (typeof body?.exit_code === "number" ? `exit code ${body.exit_code}` : null) ||
        "Install did not succeed";
      patchStatus(tool.name, {
        busy: null,
        installed,
        message: body?.ok ? null : failMsg,
      });
      setNote(
        body?.ok
          ? `“${tool.name}” is installed.`
          : `Install attempt for “${tool.name}” failed.`,
      );
    } catch (err) {
      patchStatus(tool.name, {
        busy: null,
        message: errMessage(err),
      });
    }
  }

  async function onDelete(tool: CliHostTool) {
    if (!accessToken) return;
    const ok = window.confirm(
      `Remove “${tool.name}” from the tool registry?\n\nThis does not uninstall the program from the machine; it only deletes the registry entry.`,
    );
    if (!ok) return;
    setNote(null);
    patchStatus(tool.name, { busy: "delete", message: null });
    try {
      await apiClient.delete(`/tools/${encodeURIComponent(tool.name)}`, {
        accessToken,
        clientId: tenantId,
      });
      setTools((prev) => (prev ?? []).filter((row) => row.name !== tool.name));
      setStatusByName((prev) => {
        const next = { ...prev };
        delete next[tool.name];
        return next;
      });
      setDraftByName((prev) => {
        const next = { ...prev };
        delete next[tool.name];
        return next;
      });
      if (editingName === tool.name) setEditingName(null);
      setNote(`Removed “${tool.name}” from the tool registry.`);
    } catch (err) {
      patchStatus(tool.name, {
        busy: null,
        message: errMessage(err),
      });
    }
  }

  if (!accessToken) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-body-md text-muted-foreground">
          Sign in to check and install host CLI tools.
        </CardContent>
      </Card>
    );
  }

  if (tools === undefined) {
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

  if (!tools || tools.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-body-md text-muted-foreground">
          No CLI tools in the registry yet. Register one under Tools, then return here to check or
          install it on this host.
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
                <Terminal className="h-5 w-5" />
              </span>
              <div>
                <CardTitle className="text-headline-md">CLI tools on host</CardTitle>
                <CardDescription className="mt-1">
                  {tools.length} CLI tool(s) · host {platform || "unknown"}
                  {installEnabled ? "" : " · install disabled"}
                  {checkingAll ? " · checking host…" : ""}. Use Install spec when the default
                  package id is wrong, then Install.
                </CardDescription>
              </div>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="rounded-full"
              disabled={checkingAll}
              onClick={() => void load()}
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
            <table className="w-full min-w-[880px] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-[#f8fafc]">
                  <th scope="col" className="px-6 py-3 text-label-md text-muted-foreground">
                    Tool
                  </th>
                  <th scope="col" className="px-4 py-3 text-label-md text-muted-foreground">
                    Command
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
                {tools.map((tool) => {
                  const st = statusByName[tool.name];
                  const busy = st?.busy;
                  const editing = editingName === tool.name;
                  const draft = draftByName[tool.name] ?? draftFromTool(tool);
                  let statusLabel = "Checking…";
                  if (busy === "install") statusLabel = "Installing…";
                  else if (busy === "save") statusLabel = "Saving…";
                  else if (busy === "delete") statusLabel = "Deleting…";
                  else if (st?.installed === true) statusLabel = "Installed";
                  else if (st?.installed === false) statusLabel = "Missing";
                  else if (st?.message) statusLabel = "Check failed";
                  return (
                    <tr
                      key={tool.id}
                      className="border-b border-border last:border-b-0 align-top hover:bg-muted/40"
                    >
                      <td className="px-6 py-3">
                        <p className="font-medium text-foreground">{tool.name}</p>
                        {tool.description ? (
                          <p className="mt-1 text-xs text-muted-foreground">{tool.description}</p>
                        ) : null}
                        {tool.has_install_spec ? (
                          <p className="mt-1 text-xs text-muted-foreground">
                            Spec:{" "}
                            <code className="rounded bg-muted px-1">
                              {tool.install || tool.package || "custom"}
                            </code>
                          </p>
                        ) : (
                          <p className="mt-1 text-xs text-muted-foreground">No install spec yet</p>
                        )}
                        {editing ? (
                          <div className="mt-3 space-y-3 rounded-lg border border-border bg-[#f8fafc] p-4">
                            <label className="block">
                              <span className="text-xs font-medium text-foreground">
                                Package id
                              </span>
                              <span className="mt-0.5 block text-xs text-muted-foreground">
                                Used when Install command is empty
                              </span>
                              <input
                                value={draft.package}
                                onChange={(ev) =>
                                  setDraftByName((prev) => ({
                                    ...prev,
                                    [tool.name]: { ...draft, package: ev.target.value },
                                  }))
                                }
                                placeholder="e.g. pngcheck or SomePublisher.Package"
                                disabled={busy === "save"}
                                className={cn(inputClassName, "mt-2 font-mono text-[13px]")}
                              />
                            </label>
                            <label className="block">
                              <span className="text-xs font-medium text-foreground">
                                Install command
                              </span>
                              <input
                                value={draft.install}
                                onChange={(ev) =>
                                  setDraftByName((prev) => ({
                                    ...prev,
                                    [tool.name]: { ...draft, install: ev.target.value },
                                  }))
                                }
                                placeholder="winget install -e --id …"
                                disabled={busy === "save"}
                                className={cn(inputClassName, "mt-2 font-mono text-[13px]")}
                              />
                            </label>
                            <div className="flex flex-wrap gap-2">
                              <Button
                                type="button"
                                size="sm"
                                disabled={busy === "save"}
                                onClick={() => void saveSpec(tool)}
                              >
                                {busy === "save" ? "Saving…" : "Save spec"}
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                disabled={busy === "save"}
                                onClick={() => void saveSpec(tool, { clear: true })}
                              >
                                Clear
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                disabled={busy === "save"}
                                onClick={closeSpecEditor}
                              >
                                Cancel
                              </Button>
                            </div>
                          </div>
                        ) : null}
                      </td>
                      <td className="px-4 py-3">
                        <code className="text-xs text-foreground">{tool.command ?? "—"}</code>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={installVariant(st)}>{statusLabel}</Badge>
                        {st?.message && st.installed !== true ? (
                          <p className="mt-2 text-xs text-danger">{st.message}</p>
                        ) : null}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            disabled={Boolean(busy)}
                            onClick={() => (editing ? closeSpecEditor() : openSpecEditor(tool))}
                          >
                            {editing ? "Hide spec" : "Install spec"}
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            disabled={Boolean(busy) || !installEnabled || st?.installed === true}
                            onClick={() => void onInstall(tool)}
                          >
                            {busy === "install" ? "Installing…" : "Install"}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="text-danger hover:text-danger"
                            disabled={Boolean(busy)}
                            onClick={() => void onDelete(tool)}
                          >
                            {busy === "delete" ? "Deleting…" : "Delete"}
                          </Button>
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
