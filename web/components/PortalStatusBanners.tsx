"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
};

type Banner = {
  key: string;
  tone: "warn" | "error" | "info";
  title: string;
  body: string;
  href: string;
  linkLabel: string;
};

type BillingMe = {
  plan_status: string;
};

type SlackConnection = {
  connected: boolean;
};

type SyncStatus = {
  slack_connected: boolean;
  last_failure: { error?: string | null; finished_at?: string | null } | null;
  last_success: { finished_at?: string | null } | null;
};

const TONE_BADGE: Record<Banner["tone"], "warning" | "danger" | "default"> = {
  warn: "warning",
  error: "danger",
  info: "default",
};

export function PortalStatusBanners({ accessToken, tenantId }: Props) {
  const [banners, setBanners] = useState<Banner[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!accessToken) {
      setBanners([]);
      setLoaded(true);
      return;
    }
    let cancelled = false;
    const opts = { accessToken, clientId: tenantId };
    Promise.allSettled([
      apiClient.get<BillingMe>("/billing/customers/me", {
        ...opts,
        allowStatuses: [404],
      }),
      apiClient.get<SlackConnection>("/slack/connection", opts),
      apiClient.get<SyncStatus>("/jobs/slack-history-sync/status", opts),
    ]).then((results) => {
      if (cancelled) return;
      const next: Banner[] = [];

      const billingRes = results[0];
      if (billingRes.status === "fulfilled") {
        const body = billingRes.value;
        if (body === null) {
          next.push({
            key: "unpaid",
            tone: "warn",
            title: "Plan inactive",
            body: "Subscribe so the agent, ingest, and sync entitlements can turn on.",
            href: "/app/billing",
            linkLabel: "Go to Billing",
          });
        } else if ((body.plan_status || "").toLowerCase() !== "active") {
          next.push({
            key: "unpaid",
            tone: "warn",
            title: "Plan inactive",
            body: "Your organisation plan is not active. Pay or manage your subscription to enable the agent.",
            href: "/app/billing",
            linkLabel: "Go to Billing",
          });
        }
      }

      const slackRes = results[1];
      if (slackRes.status === "fulfilled" && slackRes.value) {
        if (!slackRes.value.connected) {
          next.push({
            key: "slack",
            tone: "warn",
            title: "Slack not connected",
            body: "Install the Slack app for this organisation so mentions and history sync can run.",
            href: "/app/slack",
            linkLabel: "Connect Slack",
          });
        }
      }

      const syncRes = results[2];
      if (syncRes.status === "fulfilled" && syncRes.value) {
        const body = syncRes.value;
        const failAt = body.last_failure?.finished_at
          ? Date.parse(body.last_failure.finished_at)
          : 0;
        const okAt = body.last_success?.finished_at
          ? Date.parse(body.last_success.finished_at)
          : 0;
        if (body.last_failure && failAt >= okAt) {
          next.push({
            key: "sync",
            tone: "error",
            title: "Slack sync failed",
            body:
              body.last_failure.error ||
              "The latest history sync job failed. Retry from Knowledge.",
            href: "/app/knowledge",
            linkLabel: "Open Knowledge",
          });
        }
      }

      setBanners(next);
      setLoaded(true);
    });
    return () => {
      cancelled = true;
    };
  }, [accessToken, tenantId]);

  if (!loaded || banners.length === 0) {
    return null;
  }

  return (
    <div className="mb-8 flex flex-col gap-3">
      {banners.map((b) => (
        <Card
          key={b.key}
          className={cn(
            b.tone === "error" && "border-danger/30 bg-danger/5",
            b.tone === "warn" && "border-warning/30 bg-warning/5",
          )}
        >
          <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div role="status">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-body-md font-semibold text-foreground">{b.title}</p>
                <Badge variant={TONE_BADGE[b.tone]}>
                  {b.tone === "error" ? "Action needed" : "Setup"}
                </Badge>
              </div>
              <p className="mt-1 text-body-md text-muted-foreground">{b.body}</p>
            </div>
            <Link
              href={b.href}
              className={cn(
                buttonVariants({ variant: b.tone === "error" ? "default" : "secondary", size: "sm" }),
                "shrink-0 rounded-full",
              )}
            >
              {b.linkLabel}
            </Link>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
