"use client";

import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/dashboard/PageHeader";
import {
  IconAgent,
  IconBilling,
  IconKnowledge,
  IconSlack,
  IconTools,
  IconUsage,
} from "@/components/dashboard/icons";
import { TenantFilesPanel } from "@/components/TenantFilesPanel";
import { ApiError, apiClient } from "@/lib/api";
import {
  formatMoney,
  getMockTenantBilling,
} from "@/lib/mock/billing-data";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  accessToken: string | null;
  tenantId: string;
};

type TenantDetail = {
  id: string;
  slug: string;
  name: string;
  status: string;
  plan_status: string;
  plan_source?: string;
  override_reason?: string | null;
  external_customer_id?: string | null;
  external_subscription_id?: string | null;
  entitlements?: Record<string, unknown>;
  slack_connected: boolean;
  slack_team_id?: string | null;
  slack_team_name?: string | null;
  last_synced_at?: string | null;
  last_sync_failure_error?: string | null;
  sync_enabled?: boolean;
  sync_channel_count?: number;
  sync?: Record<string, unknown>;
};

type AuditRow = {
  id: string;
  action: string;
  actor_email?: string | null;
  created_at?: string | null;
  detail?: Record<string, unknown>;
};

type BudgetSlice = {
  key: string;
  limit: number;
  used: number;
  remaining: number;
  window: string;
};

type UsageSummary = {
  tenant_id: string;
  window: string;
  plan_active: boolean;
  budgets: BudgetSlice[];
};

const AVATAR_COLORS = [
  "bg-[#ecfdf5] text-[#006c49]",
  "bg-[#e0e7ff] text-[#4648d3]",
  "bg-[#fef9c3] text-[#854d0e]",
  "bg-[#fee2e2] text-[#991b1b]",
  "bg-[#f1f5f9] text-[#475569]",
];

const inputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

function avatarColor(name: string): string {
  const code = name.trim().charCodeAt(0) || 0;
  return AVATAR_COLORS[code % AVATAR_COLORS.length];
}

function billingControlLabel(detail: TenantDetail): string {
  if ((detail.plan_source || "stripe").toLowerCase() === "admin") {
    return "Admin waiver — Stripe webhooks do not change plan until you deactivate";
  }
  if (detail.external_subscription_id) {
    return "Payment-managed subscription";
  }
  if (detail.external_customer_id) {
    return "Payment customer (no subscription yet)";
  }
  return "Not linked to a payment provider";
}

function planLabel(planStatus: string, planSource?: string): string {
  const source = (planSource || "stripe").toLowerCase();
  if (planStatus === "active" && source === "admin") return "active · waived";
  if (planStatus === "active") return "active · paid";
  return planStatus;
}

function statusVariant(status: string): "success" | "warning" | "danger" | "muted" {
  if (status === "active") return "success";
  if (status === "suspended") return "danger";
  return "muted";
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatRelativeWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const diffMs = Date.now() - date.getTime();
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hr${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={statusVariant(status)} className="gap-1.5 capitalize">
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" aria-hidden />
      {status}
    </Badge>
  );
}

function formatCompact(value: number): string {
  if (value >= 1_000_000) {
    const compact = value / 1_000_000;
    return compact >= 10 ? `${Math.round(compact)}M` : `${compact.toFixed(1)}M`;
  }
  if (value >= 1_000) {
    const compact = value / 1_000;
    return compact >= 10 ? `${Math.round(compact)}K` : `${compact.toFixed(1)}K`;
  }
  return value.toLocaleString();
}

function budgetSlice(
  summary: UsageSummary | null | undefined,
  key: string,
): BudgetSlice | null {
  return summary?.budgets.find((row) => row.key === key) ?? null;
}

function ProgressBar({
  used,
  limit,
  barClassName,
}: {
  used: number;
  limit: number;
  barClassName?: string;
}) {
  const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
  return (
    <div className="mt-4 h-2 overflow-hidden rounded-full bg-[#f2f4f6]">
      <div
        className={cn("h-full rounded-full transition-all", barClassName ?? "bg-primary")}
        style={{ width: `${pct}%` }}
        role="progressbar"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={limit || 100}
      />
    </div>
  );
}

function SummaryStatCard({
  label,
  icon: Icon,
  footer,
  href,
  children,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  footer?: React.ReactNode;
  href?: string;
  children: React.ReactNode;
}) {
  const content = (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col pt-6">
        <div className="flex items-start justify-between gap-3">
          <p className="text-label-md text-muted-foreground">{label}</p>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
            <Icon size={18} />
          </div>
        </div>
        <div className="mt-3 flex-1">{children}</div>
        {footer ? (
          <p className="mt-3 text-sm text-muted-foreground">{footer}</p>
        ) : null}
      </CardContent>
    </Card>
  );

  if (href) {
    return (
      <Link href={href} className="block h-full transition-opacity hover:opacity-95">
        {content}
      </Link>
    );
  }

  return content;
}

function DetailRow({
  label,
  children,
  mono,
}: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 border-b border-border py-3 last:border-b-0 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <div
        className={cn(
          "text-sm font-medium text-foreground sm:text-right",
          mono && "font-mono text-[13px]",
        )}
      >
        {children}
      </div>
    </div>
  );
}

function QuickLink({
  href,
  label,
  icon: Icon,
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}) {
  return (
    <Link
      href={href}
      className="flex flex-col items-center justify-center gap-2 rounded-lg border border-border bg-card px-3 py-4 text-center text-sm font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-muted/50"
    >
      <Icon className="text-primary" size={22} />
      {label}
    </Link>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-24 animate-pulse rounded-lg bg-muted" />
      <div className="grid gap-4 lg:grid-cols-3">
        {[0, 1, 2].map((key) => (
          <div key={key} className="h-36 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {[0, 1, 2].map((key) => (
            <div key={key} className="h-48 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
        <div className="space-y-6">
          {[0, 1].map((key) => (
            <div key={key} className="h-40 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function TenantDetailPanel({ accessToken, tenantId }: Props) {
  const [detail, setDetail] = useState<TenantDetail | null>(null);
  const [logs, setLogs] = useState<AuditRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tokensDaily, setTokensDaily] = useState("");
  const [tokensMonthly, setTokensMonthly] = useState("");
  const [jobsDaily, setJobsDaily] = useState("");
  const [planReason, setPlanReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [usageMonth, setUsageMonth] = useState<UsageSummary | null>(null);
  const [usageDay, setUsageDay] = useState<UsageSummary | null>(null);
  const loadGen = useRef(0);

  const load = useCallback(async () => {
    if (!accessToken) {
      setError("Not signed in");
      setLoading(false);
      return;
    }
    const gen = ++loadGen.current;
    setError(null);
    setNotFound(false);
    setLoading(true);
    try {
      const tenantP = apiClient.get<TenantDetail>(`/admin/tenants/${tenantId}`, {
        accessToken,
        clientId: tenantId,
      });
      const auditP = apiClient
        .get<{ logs: AuditRow[] }>(
          `/admin/audit-logs?tenant_id=${encodeURIComponent(tenantId)}&limit=20`,
          { accessToken, clientId: null },
        )
        .catch(() => null);
      const usageMonthP = apiClient
        .get<UsageSummary>(`/usage/summary?window=month`, {
          accessToken,
          clientId: tenantId,
        })
        .catch(() => null);
      const usageDayP = apiClient
        .get<UsageSummary>(`/usage/summary?window=day`, {
          accessToken,
          clientId: tenantId,
        })
        .catch(() => null);

      const [tData, aData, monthUsage, dayUsage] = await Promise.all([
        tenantP,
        auditP,
        usageMonthP,
        usageDayP,
      ]);
      if (gen !== loadGen.current) return;
      if (!tData) {
        setError("Failed to load tenant");
        setDetail(null);
        return;
      }
      setDetail(tData);
      const ents = (tData.entitlements || {}) as Record<string, unknown>;
      setTokensDaily(String(ents.tokens_daily ?? ""));
      setTokensMonthly(String(ents.tokens_monthly ?? ""));
      setJobsDaily(String(ents.jobs_daily ?? ""));
      setLogs(Array.isArray(aData?.logs) ? aData.logs : []);
      setUsageMonth(monthUsage);
      setUsageDay(dayUsage);
    } catch (e) {
      if (gen !== loadGen.current) return;
      if (e instanceof ApiError && e.status === 404) {
        setNotFound(true);
        setDetail(null);
        setError(null);
      } else {
        setError(e instanceof Error ? e.message : "Request failed");
      }
    } finally {
      if (gen === loadGen.current) setLoading(false);
    }
  }, [accessToken, tenantId]);

  useEffect(() => {
    loadGen.current += 1;
    void load();
  }, [load]);

  async function setStatus(next: "active" | "suspended") {
    if (!accessToken) return;
    setBusy(true);
    setMessage(null);
    try {
      const data = await apiClient.patch<{ status: string }>(
        `/admin/tenants/${tenantId}/status`,
        { accessToken, clientId: tenantId, json: { status: next } },
      );
      setMessage(`Tenant status set to ${data?.status ?? next}`);
      await load();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Status update failed");
    } finally {
      setBusy(false);
    }
  }

  async function overridePlan(next: "active" | "inactive") {
    if (!accessToken) return;
    const reason = planReason.trim();
    if (!reason) {
      setMessage("Plan override requires a reason (audit trail)");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const data = await apiClient.patch<{ plan_status?: string; plan_source?: string }>(
        `/admin/tenants/${tenantId}/plan`,
        { accessToken, clientId: tenantId, json: { plan_status: next, reason } },
      );
      setMessage(
        `Plan set to ${data?.plan_status ?? next}` +
          (data?.plan_source ? ` (${data.plan_source}-managed)` : ""),
      );
      setPlanReason("");
      await load();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Plan override failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveBudgets() {
    if (!accessToken) return;
    setBusy(true);
    setMessage(null);
    const body: Record<string, number> = {};
    if (tokensDaily !== "") body.tokens_daily = Number(tokensDaily);
    if (tokensMonthly !== "") body.tokens_monthly = Number(tokensMonthly);
    if (jobsDaily !== "") body.jobs_daily = Number(jobsDaily);
    try {
      await apiClient.patch(`/admin/tenants/${tenantId}/budgets`, {
        accessToken,
        clientId: tenantId,
        json: body,
      });
      setMessage("Budgets updated");
      await load();
    } catch (e) {
      setMessage(e instanceof ApiError ? e.message : "Budget override failed");
    } finally {
      setBusy(false);
    }
  }

  const base = `/admin/tenants/${tenantId}`;
  const planSource = (detail?.plan_source || "stripe").toLowerCase();
  const canWaivePlan =
    detail &&
    (detail.plan_status !== "active" ||
      (detail.plan_status === "active" && planSource !== "admin"));
  const billing = getMockTenantBilling(tenantId);
  const tokenBudget = budgetSlice(usageMonth, "tokens_monthly");
  const jobsBudget = budgetSlice(usageDay, "jobs_daily");

  if (loading && !detail && !notFound) {
    return (
      <>
        <PageHeader
          title="Tenant detail"
          description="Plan, Slack connection, sync status, and support actions for this organisation."
          breadcrumbs={[
            { label: "Overview", href: "/admin" },
            { label: "Tenants", href: "/admin/tenants" },
            { label: "Detail" },
          ]}
        />
        <LoadingSkeleton />
      </>
    );
  }

  if (notFound) {
    return (
      <>
        <PageHeader
          title="Tenant detail"
          description="Plan, Slack connection, sync status, and support actions for this organisation."
          breadcrumbs={[
            { label: "Overview", href: "/admin" },
            { label: "Tenants", href: "/admin/tenants" },
            { label: "Detail" },
          ]}
        />
        <Card>
          <CardContent className="py-10 text-center">
            <p className="text-body-md text-foreground" role="alert">
              Tenant not found — the ID may be invalid.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Link href="/admin/tenants" className={buttonVariants({ variant: "outline" })}>
                Back to tenants
              </Link>
              <Link href="/admin/tenants/new" className={buttonVariants()}>
                Create tenant
              </Link>
            </div>
          </CardContent>
        </Card>
      </>
    );
  }

  return (
    <div aria-busy={busy}>
      <PageHeader
        title={detail?.name ?? "Tenant detail"}
        description="Plan, Slack connection, sync status, and support actions for this organisation."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: detail?.name ?? "Detail" },
        ]}
        actions={
          detail ? (
            <>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => void load()}
                disabled={loading || busy}
              >
                <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
                {loading ? "Loading…" : "Refresh"}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy || detail.status === "suspended"}
                onClick={() => void setStatus("suspended")}
              >
                Suspend tenant
              </Button>
              <Button
                type="button"
                disabled={busy || detail.status === "active"}
                onClick={() => void setStatus("active")}
              >
                Unsuspend tenant
              </Button>
            </>
          ) : null
        }
      >
        {detail ? (
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <span
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-lg text-sm font-semibold",
                avatarColor(detail.name),
              )}
              aria-hidden
            >
              {(detail.name.trim()[0] ?? "?").toUpperCase()}
            </span>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <span>
                Slug <code className="font-mono text-foreground">{detail.slug}</code>
              </span>
              <span className="font-mono text-[13px]">{detail.id}</span>
            </div>
          </div>
        ) : null}
      </PageHeader>

      {error ? (
        <p className="mb-6 rounded-lg border border-danger/30 bg-danger-muted px-4 py-3 text-body-md text-danger" role="alert">
          {error}
        </p>
      ) : null}

      {message ? (
        <p className="mb-6 rounded-lg border border-primary/30 bg-[#ecfdf5] px-4 py-3 text-body-md text-[#006c49]" role="status">
          {message}
        </p>
      ) : null}

      {detail ? (
        <div className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-3">
            <SummaryStatCard
              label="Billing (MRR)"
              icon={IconBilling}
              href={`${base}/billing`}
              footer={planLabel(detail.plan_status, detail.plan_source)}
            >
              <p className="flex items-baseline gap-1">
                <span className="text-3xl font-bold tracking-tight text-foreground">
                  {billing.mrrCents > 0
                    ? formatMoney(billing.mrrCents, billing.currency)
                    : "—"}
                </span>
                {billing.mrrCents > 0 ? (
                  <span className="text-lg font-medium text-muted-foreground">/mo</span>
                ) : null}
              </p>
              <ProgressBar
                used={detail.plan_status === "active" ? 1 : 0}
                limit={1}
              />
            </SummaryStatCard>

            <SummaryStatCard
              label="Token usage (month)"
              icon={IconUsage}
              href={`${base}/usage`}
              footer={
                tokenBudget && tokenBudget.limit > 0
                  ? `${Math.round((tokenBudget.used / tokenBudget.limit) * 100)}% of monthly budget`
                  : usageMonth?.plan_active
                    ? "No monthly token budget set"
                    : "Plan inactive — no budgets"
              }
            >
              <p className="flex items-baseline gap-1">
                <span className="text-3xl font-bold tracking-tight text-foreground">
                  {tokenBudget ? formatCompact(tokenBudget.used) : "—"}
                </span>
                {tokenBudget && tokenBudget.limit > 0 ? (
                  <span className="text-lg font-medium text-muted-foreground">
                    / {formatCompact(tokenBudget.limit)}
                  </span>
                ) : null}
              </p>
              {tokenBudget && tokenBudget.limit > 0 ? (
                <ProgressBar used={tokenBudget.used} limit={tokenBudget.limit} />
              ) : (
                <ProgressBar used={0} limit={1} barClassName="bg-muted" />
              )}
            </SummaryStatCard>

            <SummaryStatCard
              label="Jobs (today)"
              icon={IconAgent}
              href={`${base}/usage`}
              footer={
                jobsBudget && jobsBudget.limit > 0
                  ? `${Math.round((jobsBudget.used / jobsBudget.limit) * 100)}% of daily job budget`
                  : usageDay?.plan_active
                    ? "No daily job budget set"
                    : "Plan inactive — no budgets"
              }
            >
              <p className="flex items-baseline gap-1">
                <span className="text-3xl font-bold tracking-tight text-foreground">
                  {jobsBudget ? jobsBudget.used.toLocaleString() : "—"}
                </span>
                {jobsBudget && jobsBudget.limit > 0 ? (
                  <span className="text-lg font-medium text-muted-foreground">
                    / {formatCompact(jobsBudget.limit)}
                  </span>
                ) : null}
              </p>
              {jobsBudget && jobsBudget.limit > 0 ? (
                <ProgressBar
                  used={jobsBudget.used}
                  limit={jobsBudget.limit}
                  barClassName="bg-[#6063ee]"
                />
              ) : (
                <ProgressBar used={0} limit={1} barClassName="bg-muted" />
              )}
            </SummaryStatCard>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle>Slack &amp; sync</CardTitle>
                  <CardDescription>
                    Workspace connection and knowledge sync status for this organisation.
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <DetailRow label="Tenant ID" mono>
                    {detail.id}
                  </DetailRow>
                  <DetailRow label="Slack workspace">
                    {detail.slack_connected
                      ? `${detail.slack_team_name || "Connected"} (${detail.slack_team_id})`
                      : "Not connected"}
                  </DetailRow>
                  <DetailRow label="Last synced">
                    {formatWhen(detail.last_synced_at)}
                  </DetailRow>
                  {detail.last_sync_failure_error ? (
                    <DetailRow label="Last sync error">
                      <span className="text-danger">{detail.last_sync_failure_error}</span>
                    </DetailRow>
                  ) : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Billing &amp; access</CardTitle>
                  <CardDescription>
                    Tenant suspended blocks all usage. Plan inactive means unpaid entitlements.
                    Stripe-managed plans update via webhooks unless an admin waiver is active.
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <DetailRow label="Billing control">
                    {billingControlLabel(detail)}
                  </DetailRow>
                  {detail.override_reason ? (
                    <DetailRow label="Waiver reason">{detail.override_reason}</DetailRow>
                  ) : null}
                  {detail.external_customer_id ? (
                    <DetailRow label="Payment customer" mono>
                      {detail.external_customer_id}
                    </DetailRow>
                  ) : null}
                  {detail.external_subscription_id ? (
                    <DetailRow label="Subscription" mono>
                      {detail.external_subscription_id}
                    </DetailRow>
                  ) : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Plan override</CardTitle>
                  <CardDescription>
                    Activate to waive payment; deactivate to restore Stripe webhook control.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 pt-0">
                  <label className="block">
                    <span className="text-sm font-medium text-foreground">
                      Reason (required, audited)
                    </span>
                    <input
                      className={cn(inputClassName, "mt-2")}
                      value={planReason}
                      onChange={(e) => setPlanReason(e.target.value)}
                      placeholder="e.g. support trial, partner waiver"
                    />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      disabled={busy || !canWaivePlan}
                      onClick={() => void overridePlan("active")}
                    >
                      Activate plan (waive payment)
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy || detail.plan_status === "inactive"}
                      onClick={() => void overridePlan("inactive")}
                    >
                      Deactivate plan (restore Stripe)
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Budget override</CardTitle>
                  <CardDescription>
                    Set entitlement limits for tokens and daily jobs on this tenant.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 pt-0">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <label className="block">
                      <span className="text-sm font-medium text-foreground">tokens_daily</span>
                      <input
                        className={cn(inputClassName, "mt-2")}
                        value={tokensDaily}
                        onChange={(e) => setTokensDaily(e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="text-sm font-medium text-foreground">tokens_monthly</span>
                      <input
                        className={cn(inputClassName, "mt-2")}
                        value={tokensMonthly}
                        onChange={(e) => setTokensMonthly(e.target.value)}
                      />
                    </label>
                    <label className="block">
                      <span className="text-sm font-medium text-foreground">jobs_daily</span>
                      <input
                        className={cn(inputClassName, "mt-2")}
                        value={jobsDaily}
                        onChange={(e) => setJobsDaily(e.target.value)}
                      />
                    </label>
                  </div>
                  <Button type="button" disabled={busy} onClick={() => void saveBudgets()}>
                    Save budgets
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <TenantFilesPanel accessToken={accessToken} tenantId={tenantId} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <CardTitle>Recent audit log</CardTitle>
                    <Badge variant="muted">{logs.length}</Badge>
                  </div>
                  <CardDescription>
                    Platform owner actions recorded for this organisation.
                  </CardDescription>
                </CardHeader>
                {logs.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[520px] text-left text-sm">
                      <thead>
                        <tr className="border-b border-border bg-[#f8fafc]">
                          <th scope="col" className="px-6 py-3 text-label-md text-muted-foreground">
                            Action
                          </th>
                          <th scope="col" className="px-4 py-3 text-label-md text-muted-foreground">
                            Actor
                          </th>
                          <th scope="col" className="px-6 py-3 text-label-md text-muted-foreground">
                            When
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {logs.map((log) => (
                          <tr
                            key={log.id}
                            className="border-b border-border last:border-b-0 hover:bg-muted/40"
                          >
                            <td className="px-6 py-4 font-mono text-[13px] text-foreground">
                              {log.action}
                            </td>
                            <td className="px-4 py-4 text-foreground">
                              {log.actor_email || "—"}
                            </td>
                            <td className="px-6 py-4 text-foreground">
                              {formatWhen(log.created_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <CardContent className="pt-0">
                    <p className="rounded-lg border border-dashed border-border bg-muted/40 px-4 py-8 text-center text-body-md text-muted-foreground">
                      No audit entries for this tenant.
                    </p>
                  </CardContent>
                )}
              </Card>
            </div>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Configuration</CardTitle>
                  <CardDescription>Current tenant settings at a glance.</CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <DetailRow label="Plan">
                    <Badge variant={detail.plan_status === "active" ? "success" : "warning"}>
                      {planLabel(detail.plan_status, detail.plan_source)}
                    </Badge>
                  </DetailRow>
                  <DetailRow label="Tenant access">
                    <StatusBadge status={detail.status} />
                  </DetailRow>
                  <DetailRow label="Sync status">
                    {detail.last_sync_failure_error ? (
                      <span className="text-danger">Sync error</span>
                    ) : detail.last_synced_at ? (
                      <span className="text-[#006c49]">Healthy</span>
                    ) : (
                      "—"
                    )}
                  </DetailRow>
                  <DetailRow label="Slack">
                    {detail.slack_connected ? "Connected" : "Not connected"}
                  </DetailRow>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Tenant operations</CardTitle>
                  <CardDescription>
                    Open this tenant&apos;s org-portal surfaces as platform owner (scoped via{" "}
                    <code className="font-mono text-[13px]">X-Client-Id</code>).
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="grid grid-cols-2 gap-3">
                    <QuickLink href={`${base}/agent`} label="Agent" icon={IconAgent} />
                    <QuickLink href={`${base}/knowledge`} label="Knowledge" icon={IconKnowledge} />
                    <QuickLink href={`${base}/usage`} label="Usage" icon={IconUsage} />
                    <QuickLink href={`${base}/slack`} label="Slack" icon={IconSlack} />
                    <QuickLink href={`${base}/tools`} label="Tools" icon={IconTools} />
                    <QuickLink href={`${base}/billing`} label="Billing" icon={IconBilling} />
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <Link
                      href={`${base}/billing/invoices`}
                      className={buttonVariants({ variant: "outline", size: "sm" })}
                    >
                      Invoices
                    </Link>
                    <Link
                      href={`${base}/billing/transactions`}
                      className={buttonVariants({ variant: "outline", size: "sm" })}
                    >
                      Transactions
                    </Link>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Recent activity</CardTitle>
                  <CardDescription>Latest audited events for this tenant.</CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  {logs.length > 0 ? (
                    <ul className="space-y-4">
                      {logs.slice(0, 5).map((log) => (
                        <li key={log.id} className="flex gap-3">
                          <span
                            className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary"
                            aria-hidden
                          />
                          <div className="min-w-0 flex-1">
                            <p className="font-mono text-[13px] text-foreground">{log.action}</p>
                            <p className="mt-0.5 text-sm text-muted-foreground">
                              {log.actor_email ? `by ${log.actor_email}` : "System"}
                            </p>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              {formatRelativeWhen(log.created_at)}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-body-md text-muted-foreground">
                      No recent activity recorded.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
