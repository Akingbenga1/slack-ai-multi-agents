"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, RefreshCw, Server } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  accessToken: string | null;
};

type HealthPayload = {
  status: string;
  checks?: Record<string, { status: string; detail?: string; adapter?: string }>;
  errors?: {
    window_hours: number;
    since?: string;
    jobs_total: number;
    jobs_failed: number;
    failure_rate: number;
    failed_by_kind?: { kind: string; count: number }[];
  };
  usage?: {
    window_hours: number;
    since?: string;
    by_type?: { event_type: string; count: number }[];
  };
};

const WINDOW_OPTIONS = [
  { value: 6, label: "Last 6 hours" },
  { value: 24, label: "Last 24 hours" },
  { value: 72, label: "Last 72 hours" },
] as const;

const selectClassName =
  "rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

function labelForService(name: string): string {
  const labels: Record<string, string> = {
    postgres: "PostgreSQL",
    redis: "Redis",
    vector_store: "Vector store",
    embedding: "Embeddings (TEI)",
  };
  return labels[name] ?? name.replace(/_/g, " ");
}

function statusBannerClass(status: string): string {
  if (status === "ok") return "border-success/35 bg-success-muted/40";
  if (status === "degraded") return "border-warning/35 bg-warning-muted/40";
  return "border-danger/35 bg-danger-muted/40";
}

function statusDotClass(status: string): string {
  if (status === "ok") return "bg-success shadow-[0_0_0_4px_rgba(34,197,94,0.2)]";
  if (status === "degraded") return "bg-warning shadow-[0_0_0_4px_rgba(234,179,8,0.2)]";
  return "bg-danger shadow-[0_0_0_4px_rgba(239,68,68,0.2)]";
}

function failureRateTextClass(rate: number): string {
  if (rate === 0) return "text-success";
  if (rate < 0.05) return "text-warning";
  return "text-danger";
}

function barFillClass(rate: number, bad = false): string {
  if (bad) return "bg-danger";
  if (rate === 0) return "bg-primary";
  if (rate < 0.05) return "bg-warning";
  return "bg-danger";
}

function formatWhen(iso?: string): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return null;
  }
}

export function PlatformHealthPanel({ accessToken }: Props) {
  const [data, setData] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hours, setHours] = useState<number>(24);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) {
      setError("Not signed in");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = await apiClient.get<HealthPayload>(
        `/admin/health?hours=${hours}`,
        { accessToken, clientId: null },
      );
      setData(payload);
      setFetchedAt(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken, hours]);

  useEffect(() => {
    void load();
  }, [load]);

  const checks = Object.entries(data?.checks ?? {});
  const servicesUp = checks.filter(([, c]) => c.status === "ok").length;
  const failedKinds = data?.errors?.failed_by_kind ?? [];
  const usageRows = data?.usage?.by_type ?? [];
  const maxFailed = Math.max(1, ...failedKinds.map((r) => r.count));
  const maxUsage = Math.max(1, ...usageRows.map((r) => r.count));
  const failurePct = ((data?.errors?.failure_rate ?? 0) * 100).toFixed(1);

  return (
    <section aria-busy={loading} className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-4 pt-6">
          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="health-window" className="sr-only">
              Time window
            </label>
            <select
              id="health-window"
              className={selectClassName}
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
              disabled={loading}
            >
              {WINDOW_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="rounded-full"
              onClick={() => void load()}
              disabled={loading}
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              {loading ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
          {fetchedAt ? (
            <p className="text-sm text-muted-foreground">
              Updated {fetchedAt.toLocaleTimeString()}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {error ? (
        <p
          className="rounded-lg border border-danger-muted bg-danger-muted/40 px-4 py-3 text-body-md text-danger"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      {loading && !data ? (
        <div className="space-y-4">
          <div className="h-20 animate-pulse rounded-xl bg-muted" />
          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-xl bg-muted" />
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="h-48 animate-pulse rounded-xl bg-muted" />
            <div className="h-48 animate-pulse rounded-xl bg-muted" />
          </div>
        </div>
      ) : null}

      {data ? (
        <>
          <div
            className={cn(
              "flex items-start gap-4 rounded-xl border p-5",
              statusBannerClass(data.status),
            )}
            role="status"
          >
            <span
              className={cn("mt-1 h-3 w-3 shrink-0 rounded-full", statusDotClass(data.status))}
              aria-hidden="true"
            />
            <div>
              <p className="text-headline-md text-foreground">
                Platform {data.status === "ok" ? "healthy" : data.status}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {data.status === "ok"
                  ? "All Compose dependency probes are responding."
                  : "One or more infrastructure checks reported errors — review services below."}
                {formatWhen(data.errors?.since)
                  ? ` Window from ${formatWhen(data.errors?.since)}.`
                  : null}
              </p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-label-md text-muted-foreground">Services up</p>
                <p className="mt-2 text-headline-md text-foreground">
                  {servicesUp}/{checks.length || "—"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">Compose probes</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-label-md text-muted-foreground">Jobs run</p>
                <p className="mt-2 text-headline-md text-foreground">
                  {data.errors?.jobs_total ?? 0}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{hours}h window</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-label-md text-muted-foreground">Jobs failed</p>
                <p
                  className={cn(
                    "mt-2 text-headline-md",
                    (data.errors?.jobs_failed ?? 0) > 0 ? "text-danger" : "text-success",
                  )}
                >
                  {data.errors?.jobs_failed ?? 0}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">Across all tenants</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-label-md text-muted-foreground">Failure rate</p>
                <p
                  className={cn(
                    "mt-2 text-headline-md",
                    failureRateTextClass(data.errors?.failure_rate ?? 0),
                  )}
                >
                  {failurePct}%
                </p>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      barFillClass(data.errors?.failure_rate ?? 0),
                    )}
                    style={{ width: `${Math.min(100, Number(failurePct))}%` }}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <div className="flex items-center justify-between gap-3 border-b border-border px-6 py-5">
                <div className="flex items-center gap-2">
                  <Server className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-headline-md text-foreground">Compose services</h2>
                </div>
                <Badge variant="muted">
                  {servicesUp}/{checks.length} ok
                </Badge>
              </div>
              <CardContent className="space-y-2 pt-6">
                {checks.length > 0 ? (
                  checks.map(([name, check]) => (
                    <div
                      key={name}
                      className="flex items-start justify-between gap-3 rounded-lg border border-border bg-[#f8fafc] px-4 py-3"
                    >
                      <div>
                        <p className="text-sm font-semibold text-foreground">
                          {labelForService(name)}
                        </p>
                        {check.adapter ? (
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            Adapter: {check.adapter}
                          </p>
                        ) : null}
                        {check.detail ? (
                          <p className="mt-0.5 text-xs text-muted-foreground">{check.detail}</p>
                        ) : null}
                      </div>
                      <Badge variant={check.status === "ok" ? "success" : "danger"}>
                        {check.status}
                      </Badge>
                    </div>
                  ))
                ) : (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    No service probes returned.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <div className="flex items-center justify-between gap-3 border-b border-border px-6 py-5">
                <h2 className="text-headline-md text-foreground">Failed jobs by kind</h2>
                <Badge variant="muted">{failedKinds.length} kinds</Badge>
              </div>
              <CardContent className="px-0 pb-0 pt-0">
                {failedKinds.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-border bg-[#f8fafc]">
                          <th scope="col" className="px-6 py-3 text-label-md text-muted-foreground">
                            Job kind
                          </th>
                          <th scope="col" className="px-6 py-3 text-label-md text-muted-foreground">
                            Count
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {failedKinds.map((row) => (
                          <tr key={row.kind} className="border-b border-border last:border-b-0">
                            <td className="px-6 py-3 text-foreground">{row.kind}</td>
                            <td className="px-6 py-3">
                              <span className="font-semibold tabular-nums">{row.count}</span>
                              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                                <div
                                  className="h-full rounded-full bg-danger"
                                  style={{ width: `${(row.count / maxFailed) * 100}%` }}
                                />
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="px-6 py-8 text-center text-sm text-muted-foreground">
                    No failed jobs in this window.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <div className="flex items-center justify-between gap-3 border-b border-border px-6 py-5">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-headline-md text-foreground">Usage events</h2>
                </div>
                <Badge variant="muted">{usageRows.length} types</Badge>
              </div>
              <CardContent className="px-0 pb-0 pt-0">
                {usageRows.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-border bg-[#f8fafc]">
                          <th scope="col" className="px-6 py-3 text-label-md text-muted-foreground">
                            Event type
                          </th>
                          <th scope="col" className="px-6 py-3 text-label-md text-muted-foreground">
                            Count
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {usageRows.map((row) => (
                          <tr
                            key={row.event_type}
                            className="border-b border-border last:border-b-0"
                          >
                            <td className="px-6 py-3 text-foreground">{row.event_type}</td>
                            <td className="px-6 py-3">
                              <span className="font-semibold tabular-nums">{row.count}</span>
                              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                                <div
                                  className="h-full rounded-full bg-primary"
                                  style={{ width: `${(row.count / maxUsage) * 100}%` }}
                                />
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="px-6 py-8 text-center text-sm text-muted-foreground">
                    No usage events recorded in this window.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </section>
  );
}
