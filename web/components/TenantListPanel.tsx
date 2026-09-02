"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";
import { TenantRowMenu } from "@/components/dashboard/TenantRowMenu";
import { ApiError, apiClient } from "@/lib/api";
import { useAuthenticatedResource } from "@/lib/useAuthenticatedResource";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type TenantSummary = {
  id: string;
  slug: string;
  name: string;
  status: string;
  plan_status: string;
  plan_source?: string;
  slack_connected: boolean;
  slack_team_name?: string | null;
  last_synced_at?: string | null;
  last_sync_failure_at?: string | null;
  sync_enabled?: boolean;
  created_at?: string | null;
};

type Props = {
  accessToken: string | null;
  query?: string;
};

type PendingPlanAction = {
  tenantId: string;
  tenantName: string;
  planStatus: "active" | "inactive";
};

type PendingStatusAction = {
  tenantId: string;
  tenantName: string;
  status: "active" | "suspended";
};

const AVATAR_COLORS = [
  "bg-[#ecfdf5] text-[#006c49]",
  "bg-[#e0e7ff] text-[#4648d3]",
  "bg-[#fef9c3] text-[#854d0e]",
  "bg-[#fee2e2] text-[#991b1b]",
  "bg-[#f1f5f9] text-[#475569]",
];

function avatarColor(name: string): string {
  const code = name.trim().charCodeAt(0) || 0;
  return AVATAR_COLORS[code % AVATAR_COLORS.length];
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function formatRelativeSync(iso: string | null | undefined): string {
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

function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={statusVariant(status)} className="gap-1.5 capitalize">
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" aria-hidden />
      {status}
    </Badge>
  );
}

function TenantAvatar({ name }: { name: string }) {
  const initial = (name.trim()[0] ?? "?").toUpperCase();
  return (
    <span
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-semibold",
        avatarColor(name),
      )}
      aria-hidden
    >
      {initial}
    </span>
  );
}

export function TenantListPanel({ accessToken, query = "" }: Props) {
  const {
    data: tenants,
    error: loadError,
    busy: loading,
    reload: load,
  } = useAuthenticatedResource(
    accessToken,
    async (token) => {
      const data = await apiClient.get<{ tenants: TenantSummary[] }>(
        "/admin/tenants",
        { accessToken: token, clientId: null },
      );
      return Array.isArray(data?.tenants) ? data.tenants : [];
    },
  );

  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingPlan, setPendingPlan] = useState<PendingPlanAction | null>(null);
  const [pendingStatus, setPendingStatus] = useState<PendingStatusAction | null>(null);
  const [planReason, setPlanReason] = useState("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const tenantList = useMemo(() => {
    const all = tenants || [];
    if (!query) return all;
    return all.filter(
      (tenant) =>
        tenant.name.toLowerCase().includes(query) ||
        tenant.slug.toLowerCase().includes(query),
    );
  }, [tenants, query]);

  function clearPending() {
    setPendingPlan(null);
    setPendingStatus(null);
    setPlanReason("");
  }

  function startPlanAction(tenant: TenantSummary, planStatus: "active" | "inactive") {
    setOpenMenuId(null);
    setActionMessage(null);
    setActionError(null);
    setPendingStatus(null);
    setPendingPlan({
      tenantId: tenant.id,
      tenantName: tenant.name,
      planStatus,
    });
    setPlanReason("");
  }

  function startStatusAction(tenant: TenantSummary, status: "active" | "suspended") {
    setOpenMenuId(null);
    setActionMessage(null);
    setActionError(null);
    setPendingPlan(null);
    setPlanReason("");
    setPendingStatus({
      tenantId: tenant.id,
      tenantName: tenant.name,
      status,
    });
  }

  async function confirmPlanAction() {
    if (!accessToken || !pendingPlan) return;
    const reason = planReason.trim();
    if (!reason) {
      setActionError("Plan change requires a reason (audit trail).");
      return;
    }
    setBusyId(pendingPlan.tenantId);
    setActionError(null);
    setActionMessage(null);
    try {
      const data = await apiClient.patch<{ plan_status?: string; plan_source?: string }>(
        `/admin/tenants/${pendingPlan.tenantId}/plan`,
        {
          accessToken,
          clientId: pendingPlan.tenantId,
          json: { plan_status: pendingPlan.planStatus, reason },
        },
      );
      setActionMessage(
        `${pendingPlan.tenantName}: plan set to ${data?.plan_status ?? pendingPlan.planStatus}` +
          (data?.plan_source ? ` (${data.plan_source})` : ""),
      );
      clearPending();
      await load();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Plan update failed");
    } finally {
      setBusyId(null);
    }
  }

  async function confirmStatusAction() {
    if (!accessToken || !pendingStatus) return;
    setBusyId(pendingStatus.tenantId);
    setActionError(null);
    setActionMessage(null);
    try {
      const data = await apiClient.patch<{ status: string }>(
        `/admin/tenants/${pendingStatus.tenantId}/status`,
        {
          accessToken,
          clientId: pendingStatus.tenantId,
          json: { status: pendingStatus.status },
        },
      );
      setActionMessage(
        `${pendingStatus.tenantName}: tenant ${data?.status ?? pendingStatus.status}`,
      );
      clearPending();
      await load();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "Status update failed");
    } finally {
      setBusyId(null);
    }
  }

  const rowBusy = busyId !== null;
  const totalCount = tenants?.length ?? 0;
  const visibleCount = tenantList.length;

  return (
    <section aria-busy={loading || rowBusy}>
      {loadError ? (
        <p className="mb-4 text-body-md text-destructive" role="alert">
          {loadError}
        </p>
      ) : null}

      {actionError ? (
        <p className="mb-4 rounded-lg border border-danger-muted bg-danger-muted/40 px-4 py-3 text-body-md text-danger" role="alert">
          {actionError}
        </p>
      ) : null}

      {actionMessage ? (
        <p className="mb-4 rounded-lg border border-success-muted bg-success-muted/40 px-4 py-3 text-body-md text-success" role="status">
          {actionMessage}
        </p>
      ) : null}

      {pendingPlan ? (
        <Card className="mb-6">
          <CardContent className="space-y-4 py-6">
            <div>
              <p id="plan-confirm-title" className="text-headline-md text-foreground">
                {pendingPlan.planStatus === "inactive"
                  ? `Deactivate plan for ${pendingPlan.tenantName}`
                  : `Waive payment for ${pendingPlan.tenantName}`}
              </p>
              <p className="mt-2 text-body-md text-muted-foreground">
                {pendingPlan.planStatus === "inactive"
                  ? "Sets plan to inactive and restores Stripe webhook control. Entitlements stop until paid again."
                  : "Sets plan to active with an admin waiver — no Stripe payment required."}
              </p>
            </div>
            <label className="block text-body-md text-foreground">
              Reason (required, audited)
              <input
                value={planReason}
                onChange={(ev) => setPlanReason(ev.target.value)}
                placeholder="e.g. partner trial, support waiver, billing dispute"
                autoFocus
                className="mt-2 w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={rowBusy || !planReason.trim()}
                onClick={() => void confirmPlanAction()}
              >
                {rowBusy ? "Saving…" : "Confirm plan change"}
              </Button>
              <Button type="button" variant="secondary" disabled={rowBusy} onClick={clearPending}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {pendingStatus ? (
        <Card className="mb-6">
          <CardContent className="space-y-4 py-6">
            <div>
              <p id="status-confirm-title" className="text-headline-md text-foreground">
                {pendingStatus.status === "suspended"
                  ? `Suspend ${pendingStatus.tenantName}?`
                  : `Unsuspend ${pendingStatus.tenantName}?`}
              </p>
              <p className="mt-2 text-body-md text-muted-foreground">
                {pendingStatus.status === "suspended"
                  ? "Suspension blocks all tenant usage immediately."
                  : "Restores tenant access while plan billing rules still apply."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant={pendingStatus.status === "suspended" ? "destructive" : "default"}
                disabled={rowBusy}
                onClick={() => void confirmStatusAction()}
              >
                {rowBusy ? "Saving…" : "Confirm"}
              </Button>
              <Button type="button" variant="secondary" disabled={rowBusy} onClick={clearPending}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <div className="flex items-center justify-between gap-4 border-b border-border px-6 py-4">
          <div>
            <h2 className="text-headline-md text-foreground">All tenants</h2>
            <p className="mt-1 text-body-md text-muted-foreground">
              Click a tenant name to open details. Use the row menu (⋯) for billing and access
              actions.
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => void load()}
            disabled={loading || rowBusy}
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            {loading ? "Loading…" : "Refresh"}
          </Button>
        </div>

        {loading && tenants === undefined ? (
          <CardContent>
            <div className="space-y-3">
              {[0, 1, 2].map((key) => (
                <div key={key} className="h-14 animate-pulse rounded-lg bg-muted" />
              ))}
            </div>
          </CardContent>
        ) : tenantList.length > 0 ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-body-md">
                <thead>
                  <tr className="border-b border-border bg-[#f8fafc]">
                    <th scope="col" className="px-6 py-3 text-left text-label-md text-muted-foreground">
                      Name
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-label-md text-muted-foreground">
                      Status
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-label-md text-muted-foreground">
                      Plan
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-label-md text-muted-foreground">
                      Slack
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-label-md text-muted-foreground">
                      Created
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-label-md text-muted-foreground">
                      Last sync
                    </th>
                    <th scope="col" className="px-4 py-3 text-right text-label-md text-muted-foreground">
                      <span className="sr-only">Actions</span>
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {tenantList.map((t) => {
                    const planSource = (t.plan_source || "stripe").toLowerCase();
                    const canWaive =
                      t.plan_status !== "active" ||
                      (t.plan_status === "active" && planSource !== "admin");
                    const canDeactivate = t.plan_status === "active";
                    const isRowBusy = busyId === t.id;
                    const menuDisabled =
                      rowBusy ||
                      isRowBusy ||
                      pendingPlan !== null ||
                      pendingStatus !== null;
                    const syncFailed = Boolean(t.last_sync_failure_at);

                    return (
                      <tr
                        key={t.id}
                        className="border-b border-border transition-colors last:border-0 hover:bg-muted/60"
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <TenantAvatar name={t.name} />
                            <div className="min-w-0">
                              <Link
                                href={`/admin/tenants/${t.id}`}
                                className="font-medium text-foreground hover:text-primary"
                              >
                                {t.name}
                              </Link>
                              <p className="truncate text-sm text-muted-foreground">{t.slug}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4">
                          <StatusBadge status={t.status} />
                        </td>
                        <td className="px-4 py-4 text-foreground">
                          {planLabel(t.plan_status, t.plan_source)}
                        </td>
                        <td className="px-4 py-4 text-muted-foreground">
                          {t.slack_connected ? (
                            <span className="text-foreground">
                              {t.slack_team_name || "connected"}
                            </span>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-4 py-4 text-muted-foreground">{formatWhen(t.created_at)}</td>
                        <td className="px-4 py-4">
                          <span className={syncFailed ? "text-warning" : "text-foreground"}>
                            {formatRelativeSync(t.last_synced_at)}
                          </span>
                          {syncFailed ? (
                            <p className="mt-0.5 text-xs text-danger">sync failure</p>
                          ) : null}
                        </td>
                        <td className="px-4 py-4">
                          <TenantRowMenu
                            tenantId={t.id}
                            label={t.name}
                            open={openMenuId === t.id}
                            disabled={menuDisabled}
                            onOpenChange={(open) => setOpenMenuId(open ? t.id : null)}
                            canDeactivate={canDeactivate}
                            canWaive={canWaive}
                            tenantActive={t.status === "active"}
                            onDeactivatePlan={() => startPlanAction(t, "inactive")}
                            onWaivePayment={() => startPlanAction(t, "active")}
                            onToggleSuspend={() =>
                              startStatusAction(
                                t,
                                t.status === "active" ? "suspended" : "active",
                              )
                            }
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-border px-6 py-4 text-sm text-muted-foreground">
              <p>
                Showing {visibleCount > 0 ? `1–${visibleCount}` : "0"} of {totalCount} tenant
                {totalCount === 1 ? "" : "s"}
                {query ? " (filtered)" : ""}
              </p>
            </div>
          </>
        ) : (
          <CardContent className="py-12 text-center">
            <p className="text-body-md text-muted-foreground">
              {query ? "No tenants match your filter." : "No tenants yet."}
            </p>
            {!query ? (
              <Link
                href="/admin/tenants/new"
                className={cn(buttonVariants({ variant: "default" }), "mt-4 rounded-full")}
              >
                Create first organisation
              </Link>
            ) : null}
          </CardContent>
        )}
      </Card>
    </section>
  );
}
