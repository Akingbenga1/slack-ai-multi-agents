"use client";

import { useEffect, useState } from "react";
import { Link2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
  connectedFlag?: boolean;
  errorFlag?: string | null;
};

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  slack_denied: "Slack authorization was denied.",
  missing_code: "Slack did not return an authorization code.",
  not_configured: "Slack OAuth is not configured on the API.",
  invalid_state: "The install link expired. Click Connect Slack again from this page.",
  oauth_http_failed: "Could not complete Slack authorization. Try again.",
  oauth_access_failed: "Slack rejected the authorization request.",
  missing_token: "Slack did not return a workspace token.",
  install_failed: "Could not save the Slack installation.",
};

function oauthErrorMessage(code: string | null): string | null {
  if (!code) return null;
  return OAUTH_ERROR_MESSAGES[code] ?? "Slack connection failed. Try again.";
}

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

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function SlackConnectPanel({
  accessToken,
  tenantId,
  connectedFlag = false,
  errorFlag = null,
}: Props) {
  const [data, setData] = useState<SlackConnection | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(oauthErrorMessage(errorFlag));

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
    <div className="space-y-6">
      {connectedFlag ? (
        <p
          className="rounded-lg border border-success/20 bg-success-muted px-4 py-3 text-body-md text-success"
          role="status"
        >
          Slack workspace connected. You can reinstall if scopes change.
        </p>
      ) : null}

      {error ? (
        <p
          className="rounded-lg border border-danger-muted bg-danger-muted/40 px-4 py-3 text-body-md text-danger"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                <Link2 className="h-5 w-5" />
              </span>
              <div>
                <CardTitle className="text-headline-md">Workspace connection</CardTitle>
                <CardDescription className="mt-1">
                  Install the Slack app for this organisation to enable mentions and history sync.
                </CardDescription>
              </div>
            </div>
            {data && data !== null ? (
              <Badge variant={data.connected ? "success" : "warning"}>
                {data.connected ? "Connected" : "Not connected"}
              </Badge>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-5 pt-6">
          {data === undefined ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }, (_, key) => (
                <div key={key} className="h-10 animate-pulse rounded-lg bg-muted" />
              ))}
            </div>
          ) : data === null ? (
            <p className="text-body-md text-muted-foreground">
              Could not load connection status. Ensure the API is up and you are signed in.
            </p>
          ) : data.connected ? (
            <dl className="space-y-3 text-sm">
              <div className="flex flex-col gap-1 border-b border-border pb-3 sm:flex-row sm:justify-between">
                <dt className="text-muted-foreground">Workspace</dt>
                <dd className="font-medium text-foreground">
                  {data.team_name ?? "—"}
                  {data.team_id ? (
                    <span className="mt-1 block font-mono text-xs text-muted-foreground">
                      {data.team_id}
                    </span>
                  ) : null}
                </dd>
              </div>
              {data.installed_at ? (
                <div className="flex flex-col gap-1 border-b border-border pb-3 sm:flex-row sm:justify-between">
                  <dt className="text-muted-foreground">Installed</dt>
                  <dd className="text-foreground">{formatWhen(data.installed_at)}</dd>
                </div>
              ) : null}
              {data.scopes ? (
                <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
                  <dt className="text-muted-foreground">Scopes</dt>
                  <dd className="max-w-xl text-foreground">{data.scopes}</dd>
                </div>
              ) : null}
            </dl>
          ) : (
            <p className="text-body-md text-muted-foreground">
              No Slack workspace is linked yet. Connect to let the agent receive mentions and run
              sync jobs.
            </p>
          )}

          <div className="flex flex-wrap gap-2 border-t border-border pt-5">
            <Button
              type="button"
              className="rounded-full"
              onClick={startInstall}
              disabled={!data?.install_url}
            >
              {data?.connected ? "Reinstall Slack app" : "Connect Slack"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="py-5 text-sm text-muted-foreground">
          {data && !data.slack_configured ? (
            <p>
              API is missing <code className="rounded bg-muted px-1">SLACK_CLIENT_ID</code> — see{" "}
              <code className="rounded bg-muted px-1">docs/slack-app-setup.md</code>.
            </p>
          ) : (
            <p>
              OAuth redirect must match{" "}
              <code className="rounded bg-muted px-1">
                {"{PUBLIC_BASE_URL}/slack/oauth/callback"}
              </code>
              . After install, invite the bot to channels. Details:{" "}
              <code className="rounded bg-muted px-1">docs/slack-app-setup.md</code>.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
