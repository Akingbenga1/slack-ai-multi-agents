"use client";

import { useCallback, useEffect, useState } from "react";
import panel from "@/components/dashboard/panel.module.css";
import styles from "@/components/tools/tools.module.css";
import { ApiError, apiClient } from "@/lib/api";

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
    return <p className={panel.empty}>Sign in to check MCP server readiness.</p>;
  }
  if (servers === undefined) {
    return <p className={panel.meta}>Loading MCP servers…</p>;
  }
  if (error) {
    return <p className={panel.error}>{error}</p>;
  }

  const rows = bundled ? [bundled, ...(servers ?? [])] : (servers ?? []);
  if (rows.length === 0) {
    return (
      <p className={panel.empty}>
        No MCP servers registered yet. Create an MCP tool under Tools, then return here to verify
        the server is reachable.
      </p>
    );
  }

  return (
    <section>
      <div className={panel.toolbar}>
        <div className={panel.toolbarLeft}>
          <button
            type="button"
            disabled={checkingAll}
            onClick={() => {
              setNote(null);
              void load();
            }}
          >
            {checkingAll ? "Checking…" : "Refresh"}
          </button>
        </div>
        <p className={panel.meta}>
          {servers?.length ?? 0} registered server(s)
          {checkingAll ? " · checking…" : ""}
        </p>
      </div>

      <p className={panel.infoBanner} role="note">
        Status is checked when this page loads. Ready means this host can initialize the MCP
        session and list tools (from connection_config URL or stdio command).
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
              <th>Server</th>
              <th>Transport</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((server) => {
              const st = statusByName[server.name];
              const busy = st?.busy;
              let statusLabel = "Checking…";
              let statusClass = panel.tableMuted;
              if (busy === "check") statusLabel = "Checking…";
              else if (busy === "toggle") statusLabel = "Updating…";
              else if (st?.ready === true) {
                statusLabel =
                  typeof st.toolCount === "number"
                    ? `Ready · ${st.toolCount} tool(s)`
                    : "Ready";
                statusClass = styles.hostOk;
              } else if (st?.ready === false) {
                statusLabel = server.enabled ? "Not ready" : "Disabled";
                statusClass = styles.hostMissing;
              } else if (st?.message) {
                statusLabel = "Check failed";
                statusClass = styles.hostMissing;
              }
              return (
                <tr key={server.id}>
                  <td>
                    <div className={styles.hostToolName}>{server.name}</div>
                    {server.endpoint_hint ? (
                      <div className={panel.tableMuted}>
                        <code>{server.endpoint_hint}</code>
                      </div>
                    ) : (
                      <div className={styles.hostSpecHintMuted}>
                        No endpoint in connection config
                      </div>
                    )}
                    {server.linked_tools.length > 0 ? (
                      <div className={styles.hostSpecHint}>
                        Tools: {server.linked_tools.join(", ")}
                      </div>
                    ) : server.id === "__bundled__" ? (
                      <div className={styles.hostSpecHint}>Platform bundled MCP</div>
                    ) : (
                      <div className={styles.hostSpecHintMuted}>No linked registry tools</div>
                    )}
                  </td>
                  <td>
                    <code>{server.transport}</code>
                    {!server.enabled && server.id !== "__bundled__" ? (
                      <div className={panel.tableMuted}>disabled</div>
                    ) : null}
                  </td>
                  <td>
                    <span className={statusClass}>{statusLabel}</span>
                    {st?.message && st.ready !== true ? (
                      <div className={styles.hostMsg}>{st.message}</div>
                    ) : null}
                    {st?.detail && st.ready !== true ? (
                      <div className={styles.hostMsg}>{st.detail}</div>
                    ) : null}
                  </td>
                  <td>
                    <div className={styles.hostActions}>
                      <button
                        type="button"
                        disabled={Boolean(busy)}
                        onClick={() => void checkOne(server)}
                      >
                        {busy === "check" ? "Checking…" : "Check"}
                      </button>
                      {server.id !== "__bundled__" ? (
                        <button
                          type="button"
                          disabled={Boolean(busy)}
                          onClick={() => void onToggleEnabled(server)}
                        >
                          {busy === "toggle"
                            ? "Updating…"
                            : server.enabled
                              ? "Disable"
                              : "Enable"}
                        </button>
                      ) : null}
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
