"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import panel from "@/components/dashboard/panel.module.css";
import { apiClient } from "@/lib/api";

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

const TONE_CLASS: Record<Banner["tone"], string> = {
  warn: panel.warnBanner,
  error: panel.error,
  info: panel.infoBanner,
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
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1.25rem" }}>
      {banners.map((b) => (
        <div key={b.key} role="status" className={TONE_CLASS[b.tone]}>
          <p style={{ margin: "0 0 0.25rem", fontWeight: 600 }}>{b.title}</p>
          <p style={{ margin: "0 0 0.5rem", color: "var(--muted)" }}>{b.body}</p>
          <Link href={b.href}>{b.linkLabel}</Link>
        </div>
      ))}
    </div>
  );
}
