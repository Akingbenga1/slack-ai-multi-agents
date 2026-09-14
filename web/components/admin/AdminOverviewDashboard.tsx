"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiClient } from "@/lib/api";
import type { TenantSummary } from "@/components/TenantListPanel";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  IconAgent,
  IconBilling,
  IconCliHost,
  IconHealth,
  IconTenants,
  IconTools,
} from "@/components/dashboard/icons";

type Props = {
  accessToken: string | null;
};

type HealthPayload = {
  status: string;
  checks?: Record<string, { status: string; detail?: string; adapter?: string }>;
  errors?: {
    window_hours: number;
    jobs_total: number;
    jobs_failed: number;
    failure_rate: number;
    failed_by_kind?: { kind: string; count: number }[];
  };
};

const QUICK_LINKS = [
  {
    href: "/admin/tenants/new",
    title: "New tenant",
    icon: IconTenants,
  },
  {
    href: "/admin/tenants",
    title: "Tenants",
    icon: IconTenants,
  },
  {
    href: "/admin/billing",
    title: "Billing",
    icon: IconBilling,
  },
  {
    href: "/admin/tools",
    title: "Tools",
    icon: IconTools,
  },
  {
    href: "/admin/cli-host",
    title: "CLI host",
    icon: IconCliHost,
  },
  {
    href: "/admin/agent-trace",
    title: "Agent trace",
    icon: IconAgent,
  },
  {
    href: "/admin/health",
    title: "Platform health",
    icon: IconHealth,
  },
] as const;

function healthStatusVariant(status: string): "success" | "warning" | "danger" {
  if (status === "ok") return "success";
  if (status === "degraded") return "warning";
  return "danger";
}

function healthStatusLabel(status: string): string {
  if (status === "ok") return "Healthy";
  if (status === "degraded") return "Degraded";
  return "Down";
}

function MetricTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-border bg-[#f2f4f6] px-4 py-3">
      <p className="text-label-md text-muted-foreground">{label}</p>
      <p className="mt-2 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

/** Large hero stat — digits dominate; optional suffix (e.g. %) scales to ~55% height, top-aligned. */
function HeroMetric({
  value,
  suffix,
  className,
}: {
  value: string | number;
  suffix?: string;
  className?: string;
}) {
  return (
    <p
      className={cn(
        "flex items-start font-bold tracking-tight text-primary",
        className,
      )}
      aria-label={suffix ? `${value}${suffix}` : String(value)}
    >
      <span className="text-[3.75rem] leading-[0.95] sm:text-[4.25rem] lg:text-[4.75rem]">
        {value}
      </span>
      {suffix ? (
        <span className="ml-0.5 translate-y-1 text-[2rem] leading-none sm:text-[2.25rem] lg:text-[2.5rem]">
          {suffix}
        </span>
      ) : null}
    </p>
  );
}

function CardActionLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="shrink-0 text-sm font-medium text-primary hover:underline"
    >
      {children}
    </Link>
  );
}

export function AdminOverviewDashboard({ accessToken }: Props) {
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!accessToken) {
      setError("Sign in as platform owner to view the overview.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [healthData, tenantData] = await Promise.all([
        apiClient.get<HealthPayload>("/admin/health?hours=24", {
          accessToken,
          clientId: null,
        }),
        apiClient.get<{ tenants: TenantSummary[] }>("/admin/tenants", {
          accessToken,
          clientId: null,
        }),
      ]);
      setHealth(healthData);
      setTenants(tenantData?.tenants ?? []);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to load overview data";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void load();
  }, [load]);

  const checks = Object.entries(health?.checks ?? {});
  const servicesUp = checks.filter(([, check]) => check.status === "ok").length;
  const serviceTotal = checks.length;
  const servicePct =
    serviceTotal > 0 ? ((servicesUp / serviceTotal) * 100).toFixed(1) : "—";
  const failureRate = ((health?.errors?.failure_rate ?? 0) * 100).toFixed(2);
  const failedKinds = health?.errors?.failed_by_kind ?? [];

  const tenantStats = useMemo(() => {
    const total = tenants.length;
    const slackConnected = tenants.filter((t) => t.slack_connected).length;
    const activePlans = tenants.filter((t) => t.plan_status === "active").length;
    const suspended = tenants.filter((t) => t.status === "suspended").length;
    return { total, slackConnected, activePlans, suspended };
  }, [tenants]);

  if (loading) {
    return (
      <div className="grid gap-10 lg:grid-cols-2">
        {[0, 1, 2, 3].map((key) => (
          <Card key={key} className="min-h-52 animate-pulse bg-muted/50" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8">
          <p className="text-body-md text-destructive" role="alert">
            {error}
          </p>
          <Button type="button" variant="secondary" className="mt-4" onClick={() => void load()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-10 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Platform health</CardTitle>
            <CardDescription>
              Compose service probes, job throughput, and recent error rates across the stack.
            </CardDescription>
          </div>
          <CardActionLink href="/admin/health">View details</CardActionLink>
        </CardHeader>
        <CardContent>
          <HeroMetric value={servicePct} suffix="%" />
          <p className="mt-3 text-body-md text-muted-foreground">
            {servicesUp} of {serviceTotal || "—"} services up · status{" "}
            <Badge variant={healthStatusVariant(health?.status ?? "down")}>
              {healthStatusLabel(health?.status ?? "down")}
            </Badge>
          </p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <MetricTile label="Jobs run (24h)" value={health?.errors?.jobs_total ?? 0} />
            <MetricTile label="Failure rate" value={`${failureRate}%`} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Tenants</CardTitle>
            <CardDescription>
              Cross-tenant snapshot — plan status, Slack connections, sync health, and support
              actions.
            </CardDescription>
          </div>
          <CardActionLink href="/admin/tenants">View all</CardActionLink>
        </CardHeader>
        <CardContent>
          <HeroMetric value={tenantStats.total} />
          <p className="mt-3 text-body-md text-muted-foreground">Organisations on the platform</p>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <MetricTile label="Slack connected" value={tenantStats.slackConnected} />
            <MetricTile label="Active plans" value={tenantStats.activePlans} />
            <div className="sm:col-span-2">
              <MetricTile label="Suspended" value={tenantStats.suspended} />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Agent trace</CardTitle>
            <CardDescription>
              Run a request and inspect orchestrator prompts, plan steps, and executor answer.
            </CardDescription>
          </div>
          <CardActionLink href="/admin/agent-trace">Open trace</CardActionLink>
        </CardHeader>
        <CardContent>
          {failedKinds.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[420px] text-left text-body-md">
                <thead>
                  <tr className="border-b border-border bg-[#f8fafc]">
                    <th className="px-3 py-3 text-left text-label-md text-muted-foreground">
                      Job kind
                    </th>
                    <th className="px-3 py-3 text-left text-label-md text-muted-foreground">
                      Failures
                    </th>
                    <th className="px-3 py-3 text-left text-label-md text-muted-foreground">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {failedKinds.slice(0, 5).map((row) => (
                    <tr
                      key={row.kind}
                      className="border-b border-border transition-colors last:border-0 hover:bg-muted/60"
                    >
                      <td className="px-3 py-3 font-mono text-sm font-medium text-foreground">
                        {row.kind}
                      </td>
                      <td className="px-3 py-3 text-muted-foreground">{row.count}</td>
                      <td className="px-3 py-3">
                        <Badge variant="danger">Failed</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-4 text-body-md text-muted-foreground">
                Showing failed jobs from the last 24 hours. Open platform health for the full
                breakdown.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border bg-[#f8fafc] px-4 py-10 text-center">
              <p className="text-body-md text-muted-foreground">
                No failed jobs in the last 24 hours. Use agent trace to run and inspect a request.
              </p>
              <Link
                href="/admin/agent-trace"
                className={cn(buttonVariants({ variant: "default", size: "sm" }), "mt-4 rounded-full")}
              >
                Run agent trace
              </Link>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Quick access</CardTitle>
          <CardDescription>
            Cross-tenant oversight — plan status, Slack connections, sync health, and support
            actions.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {QUICK_LINKS.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="group flex flex-col items-center rounded-lg border border-border bg-card px-3 py-5 text-center transition-colors hover:border-primary/30 hover:bg-muted"
                >
                  <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-[#f2f4f6] text-primary">
                    <Icon size={20} />
                  </span>
                  <span className="text-sm font-medium text-foreground">{item.title}</span>
                </Link>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
