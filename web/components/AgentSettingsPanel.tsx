"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
};

type Allowlist = { channels: string[] };

type AgentConfig = {
  client_id: string;
  config_id: string;
  name: string;
  system_prompt: string | null;
  allowlist: Allowlist | null;
  schedules: {
    slack_history_sync?: { enabled: boolean };
    recurring_report?: {
      enabled: boolean;
      channel_id: string | null;
      cadence: string;
      window_label: string;
    };
  };
  updated_at: string | null;
};

async function loadConfig(
  accessToken: string,
  tenantId: string | null,
): Promise<AgentConfig> {
  const cfg = await apiClient.get<AgentConfig>("/agent/config", {
    accessToken,
    clientId: tenantId,
  });
  if (!cfg) {
    throw new Error("Empty agent config response");
  }
  return cfg;
}

export function AgentSettingsPanel({ accessToken, tenantId }: Props) {
  const [data, setData] = useState<AgentConfig | null | undefined>(undefined);
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [channelsText, setChannelsText] = useState("");
  const [syncEnabled, setSyncEnabled] = useState(true);
  const [reportEnabled, setReportEnabled] = useState(false);
  const [reportChannel, setReportChannel] = useState("");
  const [cadence, setCadence] = useState("weekly");
  const [windowLabel, setWindowLabel] = useState("last 7 days");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(undefined);
    setError(null);
    if (!accessToken) {
      setData(null);
      return;
    }
    (async () => {
      try {
        const cfg = await loadConfig(accessToken, tenantId);
        if (cancelled) return;
        setData(cfg);
        setName(cfg.name || "");
        setPrompt(cfg.system_prompt || "");
        setChannelsText((cfg.allowlist?.channels || []).join("\n"));
        setSyncEnabled(cfg.schedules?.slack_history_sync?.enabled ?? true);
        const report = cfg.schedules?.recurring_report;
        setReportEnabled(report?.enabled ?? false);
        setReportChannel(report?.channel_id || "");
        setCadence(report?.cadence || "weekly");
        setWindowLabel(report?.window_label || "last 7 days");
      } catch (err) {
        if (cancelled) return;
        setData(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, tenantId]);

  const refresh = useCallback(async () => {
    if (!accessToken) {
      setData(null);
      return;
    }
    setError(null);
    const cfg = await loadConfig(accessToken, tenantId);
    setData(cfg);
    setName(cfg.name || "");
    setPrompt(cfg.system_prompt || "");
    setChannelsText((cfg.allowlist?.channels || []).join("\n"));
    setSyncEnabled(cfg.schedules?.slack_history_sync?.enabled ?? true);
    const report = cfg.schedules?.recurring_report;
    setReportEnabled(report?.enabled ?? false);
    setReportChannel(report?.channel_id || "");
    setCadence(report?.cadence || "weekly");
    setWindowLabel(report?.window_label || "last 7 days");
  }, [accessToken, tenantId]);

  async function onSaveIdentity(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setPending(true);
    setError(null);
    setSaved(null);
    try {
      const channels = channelsText
        .split(/[\n,]+/)
        .map((c) => c.trim())
        .filter(Boolean);
      await apiClient.patch("/agent/config", {
        accessToken,
        clientId: tenantId,
        json: {
          name,
          system_prompt: prompt,
          allowlist: { channels },
        },
      });
      setSaved("Agent details saved.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPending(false);
    }
  }

  async function onSaveSchedules(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setPending(true);
    setError(null);
    setSaved(null);
    try {
      const reportBody: Record<string, unknown> = {
        enabled: reportEnabled,
        cadence,
        window_label: windowLabel,
      };
      if (reportChannel.trim()) {
        reportBody.channel_id = reportChannel.trim();
      } else {
        reportBody.clear_channel = true;
      }
      await apiClient.patch("/agent/schedules", {
        accessToken,
        clientId: tenantId,
        json: {
          slack_history_sync: { enabled: syncEnabled },
          recurring_report: reportBody,
        },
      });
      setSaved("Schedules saved.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPending(false);
    }
  }

  if (!accessToken) {
    return (
      <p style={{ color: "#b00020" }} role="status">
        API JWT missing. Start FastAPI, seed demo users, then re-login.
      </p>
    );
  }

  if (data === undefined) {
    return <p>Loading agent settings…</p>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {error ? (
        <p style={{ color: "#b00020", margin: 0 }} role="alert">
          {error}
        </p>
      ) : null}
      {saved ? (
        <p style={{ margin: 0, color: "#0b6e4f" }} role="status">
          {saved}
        </p>
      ) : null}

      <form
        onSubmit={onSaveIdentity}
        style={{ display: "grid", gap: "0.75rem", maxWidth: 560 }}
      >
        <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Identity &amp; prompt</h2>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Agent name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            style={{ padding: "0.5rem" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>System prompt (org overlay)</span>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={6}
            placeholder="Optional instructions prepended to workflow prompts"
            style={{ padding: "0.5rem", fontFamily: "inherit" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Channel allowlist (one Slack channel id per line)</span>
          <textarea
            value={channelsText}
            onChange={(e) => setChannelsText(e.target.value)}
            rows={4}
            placeholder={"C01234567\nC08999999"}
            style={{ padding: "0.5rem", fontFamily: "ui-monospace, monospace" }}
          />
        </label>
        <p style={{ margin: 0, color: "#555", fontSize: "0.85rem" }}>
          Empty allowlist = no channel restriction stored. Enforcement in Slack
          reply path can tighten later; settings are tenant-scoped today.
        </p>
        <button type="submit" disabled={pending} style={{ width: "fit-content" }}>
          {pending ? "Saving…" : "Save agent details"}
        </button>
      </form>

      <form
        onSubmit={onSaveSchedules}
        style={{ display: "grid", gap: "0.75rem", maxWidth: 560 }}
      >
        <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Jobs &amp; schedules</h2>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={syncEnabled}
            onChange={(e) => setSyncEnabled(e.target.checked)}
          />
          Enable hourly Slack history sync (Beat)
        </label>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={reportEnabled}
            onChange={(e) => setReportEnabled(e.target.checked)}
          />
          Enable recurring report job
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Report channel id</span>
          <input
            value={reportChannel}
            onChange={(e) => setReportChannel(e.target.value)}
            placeholder="C0REPORT"
            style={{ padding: "0.5rem", fontFamily: "ui-monospace, monospace" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Cadence</span>
          <select
            value={cadence}
            onChange={(e) => setCadence(e.target.value)}
            style={{ padding: "0.5rem" }}
          >
            <option value="weekly">weekly</option>
            <option value="daily">daily</option>
          </select>
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Window label</span>
          <input
            value={windowLabel}
            onChange={(e) => setWindowLabel(e.target.value)}
            style={{ padding: "0.5rem" }}
          />
        </label>
        <button type="submit" disabled={pending} style={{ width: "fit-content" }}>
          {pending ? "Saving…" : "Save schedules"}
        </button>
      </form>

      {data?.updated_at ? (
        <p style={{ margin: 0, color: "#666", fontSize: "0.85rem" }}>
          Config updated at {data.updated_at}
        </p>
      ) : null}
    </div>
  );
}
