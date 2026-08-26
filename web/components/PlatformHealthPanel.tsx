"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import styles from "./PlatformHealthPanel.module.css";

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
  if (status === "ok") return styles.statusBannerOk;
  if (status === "degraded") return styles.statusBannerDegraded;
  return styles.statusBannerDown;
}

function statusDotClass(status: string): string {
  if (status === "ok") return styles.statusDotOk;
  if (status === "degraded") return styles.statusDotDegraded;
  return styles.statusDotDown;
}

function failureRateClass(rate: number): string {
  if (rate === 0) return styles.metricValueGood;
  if (rate < 0.05) return styles.metricValueWarn;
  return styles.metricValueBad;
}

function barClass(rate: number): string {
  if (rate === 0) return styles.barFill;
  if (rate < 0.05) return `${styles.barFill} ${styles.barFillWarn}`;
  return `${styles.barFill} ${styles.barFillBad}`;
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
    <section aria-busy={loading}>
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <label htmlFor="health-window" className="sr-only">
            Time window
          </label>
          <select
            id="health-window"
            className={styles.windowSelect}
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
          <button type="button" onClick={() => void load()} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        {fetchedAt ? (
          <p className={styles.meta}>Updated {fetchedAt.toLocaleTimeString()}</p>
        ) : null}
      </div>

      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      {loading && !data ? (
        <>
          <div className={`${styles.skeleton} ${styles.skeletonBanner}`} />
          <div className={styles.metrics}>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className={`${styles.skeleton} ${styles.skeletonMetric}`} />
            ))}
          </div>
          <div className={styles.grid}>
            <div className={`${styles.skeleton} ${styles.skeletonSection}`} />
            <div className={`${styles.skeleton} ${styles.skeletonSection}`} />
          </div>
        </>
      ) : null}

      {data ? (
        <>
          <div
            className={`${styles.statusBanner} ${statusBannerClass(data.status)}`}
            role="status"
          >
            <span
              className={`${styles.statusDot} ${statusDotClass(data.status)}`}
              aria-hidden="true"
            />
            <div>
              <p className={styles.statusTitle}>
                Platform {data.status === "ok" ? "healthy" : data.status}
              </p>
              <p className={styles.statusText}>
                {data.status === "ok"
                  ? "All Compose dependency probes are responding."
                  : "One or more infrastructure checks reported errors — review services below."}
                {formatWhen(data.errors?.since)
                  ? ` Window from ${formatWhen(data.errors?.since)}.`
                  : null}
              </p>
            </div>
          </div>

          <div className={styles.metrics}>
            <div className={styles.metric}>
              <p className={styles.metricLabel}>Services up</p>
              <p className={styles.metricValue}>
                {servicesUp}/{checks.length || "—"}
              </p>
              <p className={styles.metricSub}>Compose probes</p>
            </div>
            <div className={styles.metric}>
              <p className={styles.metricLabel}>Jobs run</p>
              <p className={styles.metricValue}>{data.errors?.jobs_total ?? 0}</p>
              <p className={styles.metricSub}>{hours}h window</p>
            </div>
            <div className={styles.metric}>
              <p className={styles.metricLabel}>Jobs failed</p>
              <p
                className={`${styles.metricValue} ${
                  (data.errors?.jobs_failed ?? 0) > 0 ? styles.metricValueBad : styles.metricValueGood
                }`}
              >
                {data.errors?.jobs_failed ?? 0}
              </p>
              <p className={styles.metricSub}>Across all tenants</p>
            </div>
            <div className={styles.metric}>
              <p className={styles.metricLabel}>Failure rate</p>
              <p className={`${styles.metricValue} ${failureRateClass(data.errors?.failure_rate ?? 0)}`}>
                {failurePct}%
              </p>
              <div className={styles.barTrack} aria-hidden="true">
                <div
                  className={barClass(data.errors?.failure_rate ?? 0)}
                  style={{ width: `${Math.min(100, Number(failurePct))}%` }}
                />
              </div>
            </div>
          </div>

          <div className={styles.grid}>
            <section className={styles.section} aria-labelledby="health-services-heading">
              <div className={styles.sectionHeader}>
                <h2 id="health-services-heading" className={styles.sectionTitle}>
                  Compose services
                </h2>
                <span className={styles.sectionCount}>
                  {servicesUp}/{checks.length} ok
                </span>
              </div>
              {checks.length > 0 ? (
                <div className={styles.services}>
                  {checks.map(([name, check]) => (
                    <div key={name} className={styles.serviceRow}>
                      <div>
                        <p className={styles.serviceName}>{labelForService(name)}</p>
                        {check.adapter ? (
                          <p className={styles.serviceDetail}>Adapter: {check.adapter}</p>
                        ) : null}
                        {check.detail ? (
                          <p className={styles.serviceDetail}>{check.detail}</p>
                        ) : null}
                      </div>
                      <span
                        className={`${styles.badge} ${
                          check.status === "ok" ? styles.badgeOk : styles.badgeError
                        }`}
                      >
                        {check.status}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className={styles.empty}>No service probes returned.</p>
              )}
            </section>

            <section className={styles.section} aria-labelledby="health-failures-heading">
              <div className={styles.sectionHeader}>
                <h2 id="health-failures-heading" className={styles.sectionTitle}>
                  Failed jobs by kind
                </h2>
                <span className={styles.sectionCount}>{failedKinds.length} kinds</span>
              </div>
              {failedKinds.length > 0 ? (
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th scope="col">Job kind</th>
                        <th scope="col">Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {failedKinds.map((row) => (
                        <tr key={row.kind}>
                          <td>{row.kind}</td>
                          <td>
                            <span className={styles.tableCount}>{row.count}</span>
                            <div className={styles.barTrack} aria-hidden="true">
                              <div
                                className={styles.barFillBad}
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
                <p className={styles.empty}>No failed jobs in this window.</p>
              )}
            </section>

            <section
              className={`${styles.section} ${styles.sectionFull}`}
              aria-labelledby="health-usage-heading"
            >
              <div className={styles.sectionHeader}>
                <h2 id="health-usage-heading" className={styles.sectionTitle}>
                  Usage events
                </h2>
                <span className={styles.sectionCount}>{usageRows.length} types</span>
              </div>
              {usageRows.length > 0 ? (
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th scope="col">Event type</th>
                        <th scope="col">Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usageRows.map((row) => (
                        <tr key={row.event_type}>
                          <td>{row.event_type}</td>
                          <td>
                            <span className={styles.tableCount}>{row.count}</span>
                            <div className={styles.barTrack} aria-hidden="true">
                              <div
                                className={styles.barFill}
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
                <p className={styles.empty}>No usage events recorded in this window.</p>
              )}
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
