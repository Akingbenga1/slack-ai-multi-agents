"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
};

type SyncStatus = {
  client_id: string;
  enabled: boolean;
  slack_connected: boolean;
  last_success: { finished_at?: string | null; status?: string } | null;
  last_failure: { finished_at?: string | null; error?: string | null } | null;
  last_job: { status?: string; finished_at?: string | null } | null;
  watermarks: Record<string, unknown>;
};

export function SyncStatusPanel({ accessToken, tenantId }: Props) {
  const [data, setData] = useState<SyncStatus | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) {
      setData(null);
      return;
    }
    const status = await apiClient.get<SyncStatus>(
      "/jobs/slack-history-sync/status",
      { accessToken, clientId: tenantId },
    );
    setData(status);
  }, [accessToken, tenantId]);

  useEffect(() => {
    let cancelled = false;
    setData(undefined);
    setError(null);
    load().catch((err) => {
      if (!cancelled) {
        setData(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  async function triggerSync() {
    if (!accessToken) return;
    setPending(true);
    setError(null);
    setMessage(null);
    try {
      const body = await apiClient.post<{ task_id?: string }>(
        "/jobs/slack-history-sync",
        {
          accessToken,
          clientId: tenantId,
          json: {},
        },
      );
      setMessage(`Sync enqueued (task ${body?.task_id || "ok"}).`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <section style={{ display: "grid", gap: "0.75rem" }}>
      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Slack live sync</h2>
        <button
          type="button"
          onClick={() => triggerSync()}
          disabled={!accessToken || pending}
          style={{ padding: "0.35rem 0.6rem" }}
        >
          {pending ? "Enqueueing…" : "Trigger sync now"}
        </button>
        <button
          type="button"
          onClick={() => load().catch((err) => setError(String(err)))}
          disabled={!accessToken}
          style={{ padding: "0.35rem 0.6rem" }}
        >
          Refresh
        </button>
      </div>
      {error ? (
        <p style={{ color: "var(--error)", margin: 0 }} role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p style={{ margin: 0, color: "#0b6e4f" }} role="status">
          {message}
        </p>
      ) : null}
      {data === undefined ? (
        <p style={{ margin: 0 }}>Loading sync status…</p>
      ) : data === null ? (
        <p style={{ margin: 0, color: "var(--muted)" }}>No sync status available.</p>
      ) : (
        <>
          {!data.slack_connected ? (
            <p
              style={{
                margin: 0,
                padding: "0.75rem 1rem",
                background: "#fff7ed",
                border: "1px solid #fdba74",
                borderRadius: 4,
              }}
              role="status"
            >
              Slack is disconnected — connect the workspace before syncing.{" "}
              <a href="/app/slack">Open Slack</a>
            </p>
          ) : null}
          {data.last_failure &&
          (!data.last_success?.finished_at ||
            (data.last_failure.finished_at || "") >=
              (data.last_success.finished_at || "")) ? (
            <p
              style={{
                margin: 0,
                padding: "0.75rem 1rem",
                background: "#fef2f2",
                border: "1px solid #fca5a5",
                borderRadius: 4,
                color: "#7f1d1d",
              }}
              role="alert"
            >
              Latest sync failed
              {data.last_failure.error ? `: ${data.last_failure.error}` : "."}{" "}
              Use <strong>Trigger sync now</strong> to retry, or check{" "}
              <a href="/app/usage">Usage</a> for job errors.
            </p>
          ) : null}
          <div
            style={{
              padding: "0.75rem 1rem",
              background: "#f5f5f5",
              borderRadius: 4,
              fontSize: "0.95rem",
            }}
          >
            <p style={{ margin: "0 0 0.35rem" }}>
              Schedule: <strong>{data.enabled ? "enabled" : "disabled"}</strong>
              {" · "}
              Slack:{" "}
              <strong>{data.slack_connected ? "connected" : "not connected"}</strong>
            </p>
            <p style={{ margin: "0 0 0.35rem", fontSize: "0.85rem", color: "#444" }}>
              Last job: {data.last_job?.status || "—"}
              {data.last_job?.finished_at ? ` @ ${data.last_job.finished_at}` : ""}
            </p>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "#444" }}>
              Last success: {data.last_success?.finished_at || "—"}
              {" · "}
              Last failure: {data.last_failure?.finished_at || "—"}
              {data.last_failure?.error ? ` (${data.last_failure.error})` : ""}
            </p>
          </div>
        </>
      )}
    </section>
  );
}
