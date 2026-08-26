"use client";

import { useCallback, useEffect, useState } from "react";
import panel from "@/components/dashboard/panel.module.css";
import styles from "@/components/tools/tools.module.css";
import { ApiError, apiClient } from "@/lib/api";

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
    return <p className={panel.empty}>Sign in to check and install host CLI tools.</p>;
  }

  if (tools === undefined) {
    return <p className={panel.meta}>Loading CLI tools…</p>;
  }

  if (error) {
    return <p className={panel.error}>{error}</p>;
  }

  if (!tools || tools.length === 0) {
    return (
      <p className={panel.empty}>
        No CLI tools in the registry yet. Register one under Tools, then return here to check or
        install it on this host.
      </p>
    );
  }

  return (
    <section>
      <div className={panel.toolbar}>
        <div className={panel.toolbarLeft}>
          <button type="button" disabled={checkingAll} onClick={() => void load()}>
            {checkingAll ? "Checking…" : "Refresh"}
          </button>
        </div>
        <p className={panel.meta}>
          {tools.length} CLI tool(s) · host {platform || "unknown"}
          {installEnabled ? "" : " · install disabled"}
          {checkingAll ? " · checking host…" : ""}
        </p>
      </div>

      <p className={panel.infoBanner} role="note">
        Status is checked when this page loads. Use Install spec when the default package id is
        wrong (common with winget on Windows), then Install.
      </p>

      {note ? (
        <p className={panel.infoBanner} role="status">
          {note}
        </p>
      ) : null}

      <div className={panel.tableWrap}>
        <table className={panel.table}>
          <thead>
            <tr>
              <th>Tool</th>
              <th>Command</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {tools.map((tool) => {
              const st = statusByName[tool.name];
              const busy = st?.busy;
              const editing = editingName === tool.name;
              const draft = draftByName[tool.name] ?? draftFromTool(tool);
              let statusLabel = "Checking…";
              let statusClass = panel.tableMuted;
              if (busy === "install") {
                statusLabel = "Installing…";
              } else if (busy === "save") {
                statusLabel = "Saving…";
              } else if (busy === "delete") {
                statusLabel = "Deleting…";
              } else if (st?.installed === true) {
                statusLabel = "Installed";
                statusClass = styles.hostOk;
              } else if (st?.installed === false) {
                statusLabel = "Missing";
                statusClass = styles.hostMissing;
              } else if (st?.message) {
                statusLabel = "Check failed";
                statusClass = styles.hostMissing;
              }
              return (
                <tr key={tool.id}>
                  <td>
                    <div className={styles.hostToolName}>{tool.name}</div>
                    {tool.description ? (
                      <div className={panel.tableMuted}>{tool.description}</div>
                    ) : null}
                    {tool.has_install_spec ? (
                      <div className={styles.hostSpecHint}>
                        Spec: <code>{tool.install || tool.package || "custom"}</code>
                      </div>
                    ) : (
                      <div className={styles.hostSpecHintMuted}>No install spec yet</div>
                    )}
                    {editing ? (
                      <div className={styles.hostSpecEditor}>
                        <label className={styles.hostSpecLabel}>
                          Package id
                          <span className={styles.hostSpecHintMuted}>
                            Used when Install command is empty (winget / brew / apt default)
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
                          />
                        </label>
                        <label className={styles.hostSpecLabel}>
                          Install command
                          <span className={styles.hostSpecHintMuted}>
                            Full command, e.g. winget install -e --id Foo.Bar
                            --accept-package-agreements
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
                            className={styles.monoInput}
                            disabled={busy === "save"}
                          />
                        </label>
                        <div className={styles.hostActions}>
                          <button
                            type="button"
                            className={panel.btnPrimary}
                            disabled={busy === "save"}
                            onClick={() => void saveSpec(tool)}
                          >
                            {busy === "save" ? "Saving…" : "Save spec"}
                          </button>
                          <button
                            type="button"
                            disabled={busy === "save"}
                            onClick={() => void saveSpec(tool, { clear: true })}
                          >
                            Clear
                          </button>
                          <button
                            type="button"
                            disabled={busy === "save"}
                            onClick={closeSpecEditor}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </td>
                  <td>
                    <code>{tool.command ?? "—"}</code>
                  </td>
                  <td>
                    <span className={statusClass}>{statusLabel}</span>
                    {st?.message && st.installed !== true ? (
                      <div className={styles.hostMsg}>{st.message}</div>
                    ) : null}
                  </td>
                  <td>
                    <div className={styles.hostActions}>
                      <button
                        type="button"
                        disabled={Boolean(busy)}
                        onClick={() => (editing ? closeSpecEditor() : openSpecEditor(tool))}
                      >
                        {editing ? "Hide spec" : "Install spec"}
                      </button>
                      <button
                        type="button"
                        disabled={Boolean(busy) || !installEnabled || st?.installed === true}
                        onClick={() => void onInstall(tool)}
                      >
                        {busy === "install" ? "Installing…" : "Install"}
                      </button>
                      <button
                        type="button"
                        className={panel.btnDanger}
                        disabled={Boolean(busy)}
                        onClick={() => void onDelete(tool)}
                      >
                        {busy === "delete" ? "Deleting…" : "Delete"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
