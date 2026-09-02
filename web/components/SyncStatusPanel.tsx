"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Play, RefreshCw } from "lucide-react";
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
  slackHref?: string;
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

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function SyncStatusPanel({
  accessToken,
  tenantId,
  slackHref = "/app/slack",
}: Props) {
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

  const showFailure =
    data?.last_failure &&
    (!data.last_success?.finished_at ||
      (data.last_failure.finished_at || "") >=
        (data.last_success.finished_at || ""));

  return (
    <Card>
      <CardHeader className="border-b border-border">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-headline-md">Slack live sync</CardTitle>
            <CardDescription className="mt-1">
              Pull channel history from the connected workspace into the knowledge
              index.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => triggerSync()}
              disabled={!accessToken || pending}
              className="rounded-full"
            >
              <Play className="h-4 w-4" />
              {pending ? "Enqueueing…" : "Trigger sync"}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => load().catch((err) => setError(String(err)))}
              disabled={!accessToken}
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-6">
        {error ? (
          <p className="text-body-md text-danger" role="alert">
            {error}
          </p>
        ) : null}

        {message ? (
          <p
            className="rounded-lg border border-success/20 bg-success-muted px-4 py-3 text-body-md text-success"
            role="status"
          >
            {message}
          </p>
        ) : null}

        {data === undefined ? (
          <div className="space-y-2">
            {[0, 1].map((key) => (
              <div key={key} className="h-10 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : data === null ? (
          <p className="text-body-md text-muted-foreground">
            No sync status available.
          </p>
        ) : (
          <>
            {!data.slack_connected ? (
              <div
                className="flex items-start gap-3 rounded-lg border border-warning/30 bg-warning-muted px-4 py-3 text-body-md text-warning"
                role="status"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <p>
                  Slack is disconnected — connect the workspace before syncing.{" "}
                  <Link href={slackHref} className="font-medium underline">
                    Open Slack settings
                  </Link>
                </p>
              </div>
            ) : null}

            {showFailure ? (
              <div
                className="flex items-start gap-3 rounded-lg border border-danger/20 bg-danger-muted px-4 py-3 text-body-md text-danger"
                role="alert"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <p>
                  Latest sync failed
                  {data.last_failure?.error ? `: ${data.last_failure.error}` : "."}{" "}
                  Use <strong>Trigger sync</strong> to retry.
                </p>
              </div>
            ) : null}

            <dl className="grid gap-3 rounded-lg border border-border bg-muted/30 p-4 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <dt className="text-muted-foreground">Schedule</dt>
                <dd>
                  <Badge variant={data.enabled ? "success" : "muted"}>
                    {data.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </dd>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <dt className="text-muted-foreground">Slack workspace</dt>
                <dd>
                  <Badge variant={data.slack_connected ? "success" : "warning"}>
                    {data.slack_connected ? "Connected" : "Not connected"}
                  </Badge>
                </dd>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
                <dt className="text-muted-foreground">Last job</dt>
                <dd className="text-foreground">
                  {data.last_job?.status || "—"}
                  {data.last_job?.finished_at
                    ? ` · ${formatWhen(data.last_job.finished_at)}`
                    : ""}
                </dd>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <dt className="text-muted-foreground">Last success</dt>
                <dd className="text-foreground">
                  {formatWhen(data.last_success?.finished_at)}
                </dd>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <dt className="text-muted-foreground">Last failure</dt>
                <dd className="text-foreground">
                  {formatWhen(data.last_failure?.finished_at)}
                </dd>
              </div>
            </dl>
          </>
        )}
      </CardContent>
    </Card>
  );
}
