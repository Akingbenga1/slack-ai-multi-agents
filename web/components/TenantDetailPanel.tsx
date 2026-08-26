"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import panel from "@/components/dashboard/panel.module.css";
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
  const [notFound, setNotFound] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tokensDaily, setTokensDaily] = useState("");
  const [tokensMonthly, setTokensMonthly] = useState("");
  const [jobsDaily, setJobsDaily] = useState("");
  const [planReason, setPlanReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
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

  if (loading && !detail && !notFound) {
    return (
      <section aria-busy="true">
        <div className={`${panel.skeleton} ${panel.skeletonBlock}`} />
        <div className={panel.metrics}>
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className={`${panel.skeleton} ${panel.skeletonBlock}`} style={{ height: "4.5rem" }} />
          ))}
        </div>
      </section>
    );
  }

  if (notFound) {
    return (
      <section className={panel.section}>
        <p className={panel.error} role="alert">
          Tenant not found — the ID may be invalid.
        </p>
        <div className={panel.formRow}>
          <Link href="/admin/tenants">
            <button type="button">Back to tenants</button>
          </Link>
          <Link href="/admin/tenants/new">
            <button type="button">Create tenant</button>
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section aria-busy={busy}>
      <div className={panel.toolbar}>
        <div className={panel.toolbarLeft}>
          <button type="button" onClick={() => void load()} disabled={loading || busy}>
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
        {detail ? (
          <p className={panel.meta}>
            {detail.name} · <code>{detail.slug}</code>
          </p>
        ) : null}
      </div>

      {error ? (
        <p className={panel.error} role="alert">
          {error}
        </p>
      ) : null}

      {message ? (
        <p className={panel.infoBanner} role="status">
          {message}
        </p>
      ) : null}

      {detail ? (
        <>
          <div className={panel.metrics}>
            <div className={panel.metric}>
              <p className={panel.metricLabel}>Tenant access</p>
              <p className={`${panel.metricValue} ${detail.status === "suspended" ? panel.metricBad : panel.metricGood}`}>
                {detail.status}
              </p>
            </div>
            <div className={panel.metric}>
              <p className={panel.metricLabel}>Plan</p>
              <p className={panel.metricValue}>{detail.plan_status}</p>
              <p className={panel.metricSub}>{detail.plan_source || "stripe"}</p>
            </div>
            <div className={panel.metric}>
              <p className={panel.metricLabel}>Slack</p>
              <p className={`${panel.metricValue} ${detail.slack_connected ? panel.metricGood : panel.metricWarn}`}>
                {detail.slack_connected ? "Connected" : "Not connected"}
              </p>
            </div>
            <div className={panel.metric}>
              <p className={panel.metricLabel}>Sync channels</p>
              <p className={panel.metricValue}>{detail.sync_channel_count ?? 0}</p>
              <p className={panel.metricSub}>{detail.sync_enabled ? "enabled" : "disabled"}</p>
            </div>
          </div>

          <div className={panel.grid}>
            <section className={panel.section}>
              <div className={panel.sectionHeader}>
                <h2 className={panel.sectionTitle}>Slack &amp; sync</h2>
              </div>
              <ul className={panel.detailList}>
                <li className={panel.detailItem}>
                  <p className={panel.detailLabel}>Tenant ID</p>
                  <p className={panel.detailValue}><code>{detail.id}</code></p>
                </li>
                <li className={panel.detailItem}>
                  <p className={panel.detailLabel}>Slack workspace</p>
                  <p className={panel.detailValue}>
                    {detail.slack_connected
                      ? `${detail.slack_team_name || "connected"} (${detail.slack_team_id})`
                      : "Not connected"}
                  </p>
                </li>
                <li className={panel.detailItem}>
                  <p className={panel.detailLabel}>Last synced</p>
                  <p className={panel.detailValue}>{detail.last_synced_at || "—"}</p>
                </li>
                {detail.last_sync_failure_error ? (
                  <li className={panel.detailItem}>
                    <p className={panel.detailLabel}>Last sync error</p>
                    <p className={panel.detailValue} style={{ color: "var(--error)" }}>
                      {detail.last_sync_failure_error}
                    </p>
                  </li>
                ) : null}
              </ul>
            </section>

            <section className={panel.section}>
              <div className={panel.sectionHeader}>
                <h2 className={panel.sectionTitle}>Billing &amp; access</h2>
              </div>
              <p className={panel.sectionDesc}>
                Tenant suspended blocks all usage. Plan inactive means unpaid entitlements.
                Stripe-managed plans update via webhooks unless an admin waiver is active.
              </p>
              <ul className={panel.detailList}>
                <li className={panel.detailItem}>
                  <p className={panel.detailLabel}>Billing control</p>
                  <p className={panel.detailValue}>{billingControlLabel(detail)}</p>
                </li>
                {detail.override_reason ? (
                  <li className={panel.detailItem}>
                    <p className={panel.detailLabel}>Waiver reason</p>
                    <p className={panel.detailValue}>{detail.override_reason}</p>
                  </li>
                ) : null}
                {detail.external_customer_id ? (
                  <li className={panel.detailItem}>
                    <p className={panel.detailLabel}>Payment customer</p>
                    <p className={panel.detailValue}><code>{detail.external_customer_id}</code></p>
                  </li>
                ) : null}
                {detail.external_subscription_id ? (
                  <li className={panel.detailItem}>
                    <p className={panel.detailLabel}>Subscription</p>
                    <p className={panel.detailValue}><code>{detail.external_subscription_id}</code></p>
                  </li>
                ) : null}
              </ul>
              <div className={panel.formRow} style={{ marginTop: "0.75rem" }}>
                <Link href={`/admin/tenants/${tenantId}/tools`}>
                  <button type="button">Agent tools</button>
                </Link>
                <Link href={`/admin/tenants/${tenantId}/billing`}>
                  <button type="button">Billing overview</button>
                </Link>
                <Link href={`/admin/tenants/${tenantId}/billing/invoices`}>
                  <button type="button">Invoices</button>
                </Link>
                <Link href={`/admin/tenants/${tenantId}/billing/transactions`}>
                  <button type="button">Transactions</button>
                </Link>
              </div>
            </section>

            <section className={panel.section}>
              <div className={panel.sectionHeader}>
                <h2 className={panel.sectionTitle}>Tenant access actions</h2>
              </div>
              <div className={panel.formRow}>
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
            </section>

            <section className={panel.section}>
              <div className={panel.sectionHeader}>
                <h2 className={panel.sectionTitle}>Plan override</h2>
              </div>
              <p className={panel.sectionDesc}>
                Activate to waive payment; deactivate to restore Stripe webhook control.
              </p>
              <div className={panel.formGrid}>
                <label className={panel.formLabel}>
                  Reason (required, audited)
                  <input
                    value={planReason}
                    onChange={(e) => setPlanReason(e.target.value)}
                    placeholder="e.g. support trial, partner waiver"
                  />
                </label>
                <div className={panel.formRow}>
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
            </section>

            <section className={panel.section}>
              <div className={panel.sectionHeader}>
                <h2 className={panel.sectionTitle}>Budget override</h2>
              </div>
              <div className={panel.formGrid}>
                <label className={panel.formLabel}>
                  tokens_daily
                  <input value={tokensDaily} onChange={(e) => setTokensDaily(e.target.value)} />
                </label>
                <label className={panel.formLabel}>
                  tokens_monthly
                  <input value={tokensMonthly} onChange={(e) => setTokensMonthly(e.target.value)} />
                </label>
                <label className={panel.formLabel}>
                  jobs_daily
                  <input value={jobsDaily} onChange={(e) => setJobsDaily(e.target.value)} />
                </label>
                <div className={panel.formRow}>
                  <button type="button" disabled={busy} onClick={() => void saveBudgets()}>
                    Save budgets
                  </button>
                </div>
              </div>
            </section>

            <section className={`${panel.section} ${panel.gridFull}`}>
              <div className={panel.sectionHeader}>
                <h2 className={panel.sectionTitle}>Recent audit log</h2>
                <span className={panel.sectionCount}>{logs.length} entries</span>
              </div>
              {logs.length > 0 ? (
                <div className={panel.tableWrap}>
                  <table className={panel.table}>
                    <thead>
                      <tr>
                        <th scope="col">Action</th>
                        <th scope="col">Actor</th>
                        <th scope="col">When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logs.map((log) => (
                        <tr key={log.id}>
                          <td><code>{log.action}</code></td>
                          <td>{log.actor_email || "—"}</td>
                          <td className={panel.tableMuted}>{log.created_at || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className={panel.empty}>No audit entries for this tenant.</p>
              )}
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
