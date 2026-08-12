"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiClient } from "@/lib/api";

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

type AuditRow = {
  id: string;
  action: string;
  actor_email?: string | null;
  created_at?: string | null;
  detail?: Record<string, unknown>;
};

export function TenantDetailPanel({ accessToken, tenantId }: Props) {
  const [detail, setDetail] = useState<TenantDetail | null>(null);
  const [logs, setLogs] = useState<AuditRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tokensDaily, setTokensDaily] = useState("");
  const [tokensMonthly, setTokensMonthly] = useState("");
  const [jobsDaily, setJobsDaily] = useState("");
  const [planReason, setPlanReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const loadGen = useRef(0);

  const load = useCallback(async () => {
    if (!accessToken) {
      setError("Not signed in");
      return;
    }
    const gen = ++loadGen.current;
    setError(null);
    try {
      const tenantP = apiClient.get<TenantDetail>(`/admin/tenants/${tenantId}`, {
        accessToken,
        clientId: tenantId,
      });
      const auditP = apiClient.get<{ logs: AuditRow[] }>(
        `/admin/audit-logs?tenant_id=${encodeURIComponent(tenantId)}&limit=20`,
        { accessToken, clientId: null },
      ).catch(() => null);

      const [tData, aData] = await Promise.all([tenantP, auditP]);
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
    } catch (e) {
      if (gen !== loadGen.current) return;
      setError(e instanceof Error ? e.message : "Request failed");
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
        {
          accessToken,
          clientId: tenantId,
          json: { status: next },
        },
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
      const data = await apiClient.patch<{
        plan_status?: string;
        plan_source?: string;
      }>(`/admin/tenants/${tenantId}/plan`, {
        accessToken,
        clientId: tenantId,
        json: { plan_status: next, reason },
      });
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

  if (!detail && !error) {
    return <p>Loading tenant…</p>;
  }

  return (
    <section>
      <p>
        <Link href="/admin/tenants">← Tenants</Link>
      </p>
      {error ? (
        <p style={{ color: "#b00020" }} role="alert">
          {error}
        </p>
      ) : null}
      {detail ? (
        <>
          <h2 style={{ marginTop: 0 }}>
            {detail.name}{" "}
            <span style={{ fontWeight: 400, color: "#555" }}>
              ({detail.slug})
            </span>
          </h2>
          <ul style={{ lineHeight: 1.7 }}>
            <li>
              <strong>id:</strong> <code>{detail.id}</code>
            </li>
            <li>
              <strong>Slack:</strong>{" "}
              {detail.slack_connected
                ? `${detail.slack_team_name || "connected"} (${detail.slack_team_id})`
                : "not connected"}
            </li>
            <li>
              <strong>Sync enabled:</strong> {String(!!detail.sync_enabled)} ·
              channels {detail.sync_channel_count ?? 0}
            </li>
            <li>
              <strong>Last synced:</strong> {detail.last_synced_at || "—"}
            </li>
            {detail.last_sync_failure_error ? (
              <li style={{ color: "#b00020" }}>
                Last sync error: {detail.last_sync_failure_error}
              </li>
            ) : null}
          </ul>

          <h3>Billing &amp; access</h3>
          <p style={{ fontSize: "0.9rem", color: "#444", maxWidth: 640 }}>
            These are separate controls: <strong>tenant suspended</strong> is a
            hard block on all usage; <strong>plan inactive</strong> means unpaid
            or waived entitlements; <strong>Stripe-managed</strong> means
            webhooks can change plan status unless an admin waiver is active.
          </p>
          <ul style={{ lineHeight: 1.7 }}>
            <li>
              <strong>Tenant access:</strong>{" "}
              <span
                style={{
                  color: detail.status === "suspended" ? "#b00020" : undefined,
                }}
              >
                {detail.status}
              </span>
              {detail.status === "suspended"
                ? " — blocks agent, ingest, and sync regardless of plan"
                : " — organisation can use entitled features"}
            </li>
            <li>
              <strong>Plan entitlements:</strong> {detail.plan_status}
              {detail.plan_status === "active"
                ? " — agent / ingest / sync enabled (if tenant not suspended)"
                : " — payment required or waived off"}
            </li>
            <li>
              <strong>Billing control:</strong> {billingControlLabel(detail)}
            </li>
            {detail.override_reason ? (
              <li>
                <strong>Waiver reason:</strong> {detail.override_reason}
              </li>
            ) : null}
            {detail.external_customer_id ? (
              <li>
                <strong>Payment customer:</strong>{" "}
                <code>{detail.external_customer_id}</code>
              </li>
            ) : null}
            {detail.external_subscription_id ? (
              <li>
                <strong>Subscription:</strong>{" "}
                <code>{detail.external_subscription_id}</code>
              </li>
            ) : null}
          </ul>

          <h3>Tenant access actions</h3>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button
              type="button"
              disabled={busy || detail.status === "suspended"}
              onClick={() => void setStatus("suspended")}
            >
              Suspend tenant
            </button>
            <button
              type="button"
              disabled={busy || detail.status === "active"}
              onClick={() => void setStatus("active")}
            >
              Unsuspend tenant
            </button>
          </div>

          <h3 style={{ marginTop: "1.25rem" }}>Plan override (no Stripe)</h3>
          <p style={{ fontSize: "0.9rem", color: "#444", maxWidth: 640 }}>
            Activate to waive payment for this org; deactivate to restore
            Stripe webhook control. Does not change tenant suspended status.
          </p>
          <div
            style={{
              display: "grid",
              gap: "0.5rem",
              maxWidth: 420,
            }}
          >
            <label>
              Reason (required, audited){" "}
              <input
                value={planReason}
                onChange={(e) => setPlanReason(e.target.value)}
                placeholder="e.g. support trial, partner waiver"
                style={{ width: "100%" }}
              />
            </label>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button
                type="button"
                disabled={
                  busy ||
                  (detail.plan_status === "active" &&
                    (detail.plan_source || "stripe").toLowerCase() === "admin")
                }
                onClick={() => void overridePlan("active")}
              >
                Activate plan (waive payment)
              </button>
              <button
                type="button"
                disabled={busy || detail.plan_status === "inactive"}
                onClick={() => void overridePlan("inactive")}
              >
                Deactivate plan (restore Stripe)
              </button>
            </div>
          </div>

          <h3 style={{ marginTop: "1.25rem" }}>Budget override</h3>
          <div
            style={{
              display: "grid",
              gap: "0.5rem",
              maxWidth: 320,
            }}
          >
            <label>
              tokens_daily{" "}
              <input
                value={tokensDaily}
                onChange={(e) => setTokensDaily(e.target.value)}
              />
            </label>
            <label>
              tokens_monthly{" "}
              <input
                value={tokensMonthly}
                onChange={(e) => setTokensMonthly(e.target.value)}
              />
            </label>
            <label>
              jobs_daily{" "}
              <input
                value={jobsDaily}
                onChange={(e) => setJobsDaily(e.target.value)}
              />
            </label>
            <button type="button" disabled={busy} onClick={() => void saveBudgets()}>
              Save budgets
            </button>
          </div>

          {message ? <p>{message}</p> : null}

          <h3 style={{ marginTop: "1.25rem" }}>Recent audit log</h3>
          {logs.length === 0 ? (
            <p>No audit entries for this tenant.</p>
          ) : (
            <ul style={{ fontSize: "0.9rem", lineHeight: 1.6 }}>
              {logs.map((log) => (
                <li key={log.id}>
                  <code>{log.action}</code> · {log.actor_email || "—"} ·{" "}
                  {log.created_at || "—"}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </section>
  );
}
