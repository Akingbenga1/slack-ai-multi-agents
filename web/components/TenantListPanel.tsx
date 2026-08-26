"use client";

import Link from "next/link";
import { useState } from "react";
import panel from "@/components/dashboard/panel.module.css";
import { TenantRowMenu } from "@/components/dashboard/TenantRowMenu";
import { ApiError, apiClient } from "@/lib/api";
import { useAuthenticatedResource } from "@/lib/useAuthenticatedResource";

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

function statusBadge(status: string): string {
  if (status === "active") return panel.badgeOk;
  if (status === "suspended") return panel.badgeError;
  return panel.badgeNeutral;
}

function planBadge(plan: string): string {
  if (plan === "active") return panel.badgeOk;
  return panel.badgeWarn;
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

function planLabel(planStatus: string, planSource?: string): string {
  const source = (planSource || "stripe").toLowerCase();
  if (planStatus === "active" && source === "admin") return "active · waived";
  if (planStatus === "active") return "active · paid";
  return planStatus;
}

export function TenantListPanel({ accessToken }: Props) {
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

  const tenantList = tenants || [];

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

  return (
    <section aria-busy={loading || rowBusy}>
      <div className={panel.toolbar}>
        <div className={panel.toolbarLeft}>
          <Link href="/admin/tenants/new">
            <button type="button">New tenant</button>
          </Link>
          <button type="button" onClick={() => void load()} disabled={loading || rowBusy}>
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
        {tenantList.length > 0 ? (
          <p className={panel.meta}>{tenantList.length} organisation(s)</p>
        ) : null}
      </div>

      {loadError ? (
        <p className={panel.error} role="alert">
          {loadError}
        </p>
      ) : null}

      {actionError ? (
        <p className={panel.error} role="alert">
          {actionError}
        </p>
      ) : null}

      {actionMessage ? (
        <p className={panel.success} role="status">
          {actionMessage}
        </p>
      ) : null}

      {pendingPlan ? (
        <div className={panel.confirmBanner} role="dialog" aria-labelledby="plan-confirm-title">
          <p id="plan-confirm-title" className={panel.confirmTitle}>
            {pendingPlan.planStatus === "inactive"
              ? `Deactivate plan for ${pendingPlan.tenantName}`
              : `Waive payment for ${pendingPlan.tenantName}`}
          </p>
          <p className={panel.confirmDesc}>
            {pendingPlan.planStatus === "inactive"
              ? "Sets plan to inactive and restores Stripe webhook control. Entitlements stop until paid again."
              : "Sets plan to active with an admin waiver — no Stripe payment required."}
          </p>
          <label className={panel.formLabel}>
            Reason (required, audited)
            <input
              value={planReason}
              onChange={(ev) => setPlanReason(ev.target.value)}
              placeholder="e.g. partner trial, support waiver, billing dispute"
              autoFocus
            />
          </label>
          <div className={panel.formRow}>
            <button
              type="button"
              className={panel.btnPrimary}
              disabled={rowBusy || !planReason.trim()}
              onClick={() => void confirmPlanAction()}
            >
              {rowBusy ? "Saving…" : "Confirm plan change"}
            </button>
            <button type="button" disabled={rowBusy} onClick={clearPending}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {pendingStatus ? (
        <div className={panel.confirmBanner} role="dialog" aria-labelledby="status-confirm-title">
          <p id="status-confirm-title" className={panel.confirmTitle}>
            {pendingStatus.status === "suspended"
              ? `Suspend ${pendingStatus.tenantName}?`
              : `Unsuspend ${pendingStatus.tenantName}?`}
          </p>
          <p className={panel.confirmDesc}>
            {pendingStatus.status === "suspended"
              ? "Suspension blocks all tenant usage immediately."
              : "Restores tenant access while plan billing rules still apply."}
          </p>
          <div className={panel.formRow}>
            <button
              type="button"
              className={pendingStatus.status === "suspended" ? panel.btnDanger : panel.btnPrimary}
              disabled={rowBusy}
              onClick={() => void confirmStatusAction()}
            >
              {rowBusy ? "Saving…" : "Confirm"}
            </button>
            <button type="button" disabled={rowBusy} onClick={clearPending}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      <section className={panel.section}>
        <div className={panel.sectionHeader}>
          <h2 className={panel.sectionTitle}>All tenants</h2>
          <span className={panel.sectionCount}>{tenantList.length}</span>
        </div>
        <p className={panel.sectionDesc}>
          Click a tenant name to open details. Use the row menu (⋯) for billing and access actions.
        </p>

        {loading && tenants === undefined ? (
          <div className={`${panel.skeleton} ${panel.skeletonBlock}`} />
        ) : tenantList.length > 0 ? (
          <div className={`${panel.tableWrap} ${openMenuId ? panel.tableWrapMenuOpen : ""}`}>
            <table className={panel.table}>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Status</th>
                  <th scope="col">Plan</th>
                  <th scope="col">Slack</th>
                  <th scope="col">Created</th>
                  <th scope="col">Last sync</th>
                  <th scope="col" className={panel.actionsCell}>
                    <span className="sr-only">Actions</span>
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

                  return (
                    <tr key={t.id}>
                      <td>
                        <Link href={`/admin/tenants/${t.id}`} className={panel.tableLink}>
                          {t.name}
                        </Link>
                        <div className={panel.tableMuted}>{t.slug}</div>
                      </td>
                      <td>
                        <span className={`${panel.badge} ${statusBadge(t.status)}`}>
                          {t.status}
                        </span>
                      </td>
                      <td>
                        <span className={`${panel.badge} ${planBadge(t.plan_status)}`}>
                          {planLabel(t.plan_status, t.plan_source)}
                        </span>
                      </td>
                      <td>
                        {t.slack_connected ? (
                          <span className={`${panel.badge} ${panel.badgeOk}`}>
                            {t.slack_team_name || "connected"}
                          </span>
                        ) : (
                          <span className={`${panel.badge} ${panel.badgeNeutral}`}>—</span>
                        )}
                      </td>
                      <td className={panel.tableMuted}>{formatWhen(t.created_at)}</td>
                      <td>
                        <span className={panel.tableMuted}>{t.last_synced_at || "—"}</span>
                        {t.last_sync_failure_at ? (
                          <div className={panel.tableMuted} style={{ color: "var(--error)" }}>
                            sync failure
                          </div>
                        ) : null}
                      </td>
                      <td className={panel.actionsCell}>
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
                            startStatusAction(t, t.status === "active" ? "suspended" : "active")
                          }
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className={panel.empty}>
            <p style={{ margin: "0 0 0.75rem" }}>No tenants yet.</p>
            <Link href="/admin/tenants/new">
              <button type="button">Create first organisation</button>
            </Link>
          </div>
        )}
      </section>
    </section>
  );
}
