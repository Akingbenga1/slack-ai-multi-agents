"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
  connectedFlag?: boolean;
  errorFlag?: string | null;
};

type SlackConnection = {
  connected: boolean;
  client_id: string;
  team_id: string | null;
  team_name: string | null;
  scopes: string | null;
  installed_at: string | null;
  install_url: string;
  slack_configured: boolean;
};

async function fetchConnection(
  accessToken: string,
  tenantId: string | null,
): Promise<SlackConnection> {
  const data = await apiClient.get<SlackConnection>("/slack/connection", {
    accessToken,
    clientId: tenantId,
  });
  if (!data) {
    throw new Error("Empty slack connection response");
  }
  return data;
}

export function SlackConnectPanel({
  accessToken,
  tenantId,
  connectedFlag = false,
  errorFlag = null,
}: Props) {
  const [data, setData] = useState<SlackConnection | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(errorFlag);

  useEffect(() => {
    if (!accessToken) {
      setData(null);
      return;
    }
    let cancelled = false;
    fetchConnection(accessToken, tenantId)
      .then((row) => {
        if (!cancelled) setData(row);
      })
      .catch((err) => {
        if (!cancelled) {
          setData(null);
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, tenantId]);

  function startInstall() {
    if (!data?.install_url) {
      setError("Install URL unavailable — check API PUBLIC_BASE_URL and Slack client id.");
      return;
    }
    window.location.href = data.install_url;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {connectedFlag ? (
        <p
          style={{
            margin: 0,
            padding: "0.75rem 1rem",
            background: "#e8f5e9",
            borderRadius: 4,
          }}
        >
          Slack workspace connected. You can reinstall if scopes change.
        </p>
      ) : null}
      {error ? (
        <p style={{ color: "#b00020", margin: 0 }} role="alert">
          {error}
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
        {data === undefined ? (
          <p style={{ margin: 0 }}>Loading Slack connection…</p>
        ) : data === null ? (
          <p style={{ margin: 0 }}>
            Could not load connection status. Ensure the API is up and you are
            signed in.
          </p>
        ) : data.connected ? (
          <>
            <p style={{ margin: "0 0 0.35rem" }}>
              Status: <strong style={{ color: "#1b5e20" }}>connected</strong>
              {data.team_name ? ` · ${data.team_name}` : ""}
              {data.team_id ? ` (${data.team_id})` : ""}
            </p>
            {data.installed_at ? (
              <p style={{ margin: "0 0 0.35rem", color: "#555", fontSize: "0.85rem" }}>
                Installed {data.installed_at}
              </p>
            ) : null}
            {data.scopes ? (
              <p style={{ margin: 0, color: "#444", fontSize: "0.85rem" }}>
                Scopes: {data.scopes}
              </p>
            ) : null}
          </>
        ) : (
          <p style={{ margin: 0 }}>
            Status: <strong style={{ color: "#9a3412" }}>not connected</strong>
            {" — "}
            install the Slack app for this organisation to enable mentions and sync.
          </p>
        )}
      </div>

      <div>
        <button
          type="button"
          onClick={startInstall}
          disabled={!data?.install_url}
          style={{ padding: "0.5rem 1rem", cursor: "pointer" }}
        >
          {data?.connected ? "Reinstall Slack app" : "Connect Slack"}
        </button>
      </div>

      {data && !data.slack_configured ? (
        <p style={{ margin: 0, color: "#555", fontSize: "0.9rem" }}>
          API is missing <code>SLACK_CLIENT_ID</code> — see{" "}
          <code>docs/slack-app-setup.md</code>.
        </p>
      ) : (
        <p style={{ margin: 0, color: "#555", fontSize: "0.9rem" }}>
          OAuth redirect must match{" "}
          <code>{"{PUBLIC_BASE_URL}/slack/oauth/callback"}</code>. After install,
          invite the bot to channels. Details:{" "}
          <code>docs/slack-app-setup.md</code>.
        </p>
      )}
    </div>
  );
}
