"use client";

import { useEffect, useState } from "react";
import { apiAuthHeaders, getApiBaseUrl } from "@/lib/api";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
};

type EventAgg = {
  event_type: string;
  event_count: number;
  units: number;
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
  since: string;
  as_of: string;
  by_event_type: EventAgg[];
  totals: { event_count: number; units: number };
  plan_active: boolean;
  budgets: BudgetSlice[];
};

type UsageEventRow = {
  id: string;
  event_type: string;
  units: number;
  meta: Record<string, unknown>;
  created_at: string | null;
};

type JobLogRow = {
  id: string;
  kind: string;
  status: string;
  error: string | null;
  created_at: string | null;
  finished_at: string | null;
};

async function fetchSummary(
  accessToken: string,
  tenantId: string | null,
  window: "day" | "month",
): Promise<UsageSummary> {
  const headers = apiAuthHeaders(accessToken, tenantId);
  const res = await fetch(
    `${getApiBaseUrl()}/usage/summary?window=${window}`,
    { headers },
  );
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return (await res.json()) as UsageSummary;
}

async function fetchEvents(
  accessToken: string,
  tenantId: string | null,
  eventType: string,
): Promise<UsageEventRow[]> {
  const headers = apiAuthHeaders(accessToken, tenantId);
  const q = eventType
    ? `?event_type=${encodeURIComponent(eventType)}&limit=40`
    : "?limit=40";
  const res = await fetch(`${getApiBaseUrl()}/usage/events${q}`, { headers });
  if (!res.ok) {
    throw new Error((await res.text()) || res.statusText);
  }
  const body = (await res.json()) as { events: UsageEventRow[] };
  return body.events;
}

async function fetchJobs(
  accessToken: string,
  tenantId: string | null,
  failedOnly: boolean,
): Promise<JobLogRow[]> {
  const headers = apiAuthHeaders(accessToken, tenantId);
  const q = failedOnly ? "?status=failed&limit=40" : "?limit=40";
  const res = await fetch(`${getApiBaseUrl()}/usage/jobs${q}`, { headers });
  if (!res.ok) {
    throw new Error((await res.text()) || res.statusText);
  }
  const body = (await res.json()) as { jobs: JobLogRow[] };
  return body.jobs;
}

export function UsageSummaryPanel({ accessToken, tenantId }: Props) {
  const [window, setWindow] = useState<"day" | "month">("day");
  const [eventFilter, setEventFilter] = useState<string>("");
  const [failedOnly, setFailedOnly] = useState(false);
  const [data, setData] = useState<UsageSummary | null | undefined>(undefined);
  const [events, setEvents] = useState<UsageEventRow[] | null>(null);
  const [jobs, setJobs] = useState<JobLogRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setData(null);
      setEvents(null);
      setJobs(null);
      return;
    }
    let cancelled = false;
    setData(undefined);
    setError(null);
    Promise.all([
      fetchSummary(accessToken, tenantId, window),
      fetchEvents(accessToken, tenantId, eventFilter),
      fetchJobs(accessToken, tenantId, failedOnly),
    ])
      .then(([summary, ev, jb]) => {
        if (!cancelled) {
          setData(summary);
          setEvents(ev);
          setJobs(jb);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setData(null);
          setEvents(null);
          setJobs(null);
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, tenantId, window, eventFilter, failedOnly]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <label htmlFor="usage-window">Window</label>
        <select
          id="usage-window"
          value={window}
          onChange={(e) => setWindow(e.target.value as "day" | "month")}
          style={{ padding: "0.35rem 0.5rem" }}
        >
          <option value="day">UTC day</option>
          <option value="month">UTC month</option>
        </select>
        <label htmlFor="event-filter">Event type</label>
        <select
          id="event-filter"
          value={eventFilter}
          onChange={(e) => setEventFilter(e.target.value)}
          style={{ padding: "0.35rem 0.5rem" }}
        >
          <option value="">All events</option>
          <option value="slack_mention">Mentions</option>
          <option value="llm_tokens">Token usage</option>
          <option value="job">Jobs</option>
          <option value="sync_run">Sync runs</option>
          <option value="ingest">Ingest</option>
          <option value="report_post">Report posts</option>
        </select>
        <label style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={failedOnly}
            onChange={(e) => setFailedOnly(e.target.checked)}
          />
          Failed jobs only
        </label>
      </div>

      {error ? (
        <p style={{ color: "#b00020", margin: 0 }} role="alert">
          {error}
        </p>
      ) : null}

      {data === undefined ? (
        <p style={{ margin: 0 }}>Loading usage…</p>
      ) : data === null ? (
        <p style={{ margin: 0 }}>
          No usage data. Sign in with an API token and ensure the gateway is up.
        </p>
      ) : (
        <>
          <div
            style={{
              padding: "0.75rem 1rem",
              background: "#f5f5f5",
              borderRadius: 4,
              fontSize: "0.95rem",
            }}
          >
            <p style={{ margin: "0 0 0.35rem" }}>
              Plan: <strong>{data.plan_active ? "active" : "inactive"}</strong>
              {" · "}
              Events: {data.totals.event_count} · Units: {data.totals.units}
            </p>
            <p style={{ margin: 0, color: "#444", fontSize: "0.85rem" }}>
              Since {data.since} · as of {data.as_of}
            </p>
          </div>

          <section>
            <h2 style={{ fontSize: "1.1rem", margin: "0 0 0.5rem" }}>Budgets</h2>
            {data.budgets.every((b) => b.limit === 0) ? (
              <p style={{ margin: 0, color: "#555" }}>
                No budgets while the plan is inactive — subscribe under Billing.
              </p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                {data.budgets.map((b) => (
                  <li key={b.key}>
                    {b.key}: {b.used} / {b.limit} used ({b.remaining} remaining,{" "}
                    {b.window})
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h2 style={{ fontSize: "1.1rem", margin: "0 0 0.5rem" }}>By event type</h2>
            {data.by_event_type.length === 0 ? (
              <p style={{ margin: 0, color: "#555" }}>No events in this window.</p>
            ) : (
              <table style={{ borderCollapse: "collapse", width: "100%", maxWidth: 480 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "0.35rem 0.5rem" }}>
                      Type
                    </th>
                    <th style={{ textAlign: "right", padding: "0.35rem 0.5rem" }}>
                      Count
                    </th>
                    <th style={{ textAlign: "right", padding: "0.35rem 0.5rem" }}>
                      Units
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_event_type.map((r) => (
                    <tr key={r.event_type}>
                      <td style={{ padding: "0.35rem 0.5rem" }}>{r.event_type}</td>
                      <td style={{ padding: "0.35rem 0.5rem", textAlign: "right" }}>
                        {r.event_count}
                      </td>
                      <td style={{ padding: "0.35rem 0.5rem", textAlign: "right" }}>
                        {r.units}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section>
            <h2 style={{ fontSize: "1.1rem", margin: "0 0 0.5rem" }}>
              Recent events
            </h2>
            {!events || events.length === 0 ? (
              <p style={{ margin: 0, color: "#555" }}>No recent usage events.</p>
            ) : (
              <table style={{ borderCollapse: "collapse", width: "100%" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "0.35rem 0.5rem" }}>
                      When
                    </th>
                    <th style={{ textAlign: "left", padding: "0.35rem 0.5rem" }}>
                      Type
                    </th>
                    <th style={{ textAlign: "right", padding: "0.35rem 0.5rem" }}>
                      Units
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e) => (
                    <tr key={e.id}>
                      <td style={{ padding: "0.35rem 0.5rem", fontSize: "0.85rem" }}>
                        {e.created_at || "—"}
                      </td>
                      <td style={{ padding: "0.35rem 0.5rem" }}>{e.event_type}</td>
                      <td style={{ padding: "0.35rem 0.5rem", textAlign: "right" }}>
                        {e.units}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section>
            <h2 style={{ fontSize: "1.1rem", margin: "0 0 0.5rem" }}>
              Recent jobs {failedOnly ? "(errors)" : ""}
            </h2>
            {!jobs || jobs.length === 0 ? (
              <p style={{ margin: 0, color: "#555" }}>
                {failedOnly ? "No failed jobs." : "No recent jobs."}
              </p>
            ) : (
              <table style={{ borderCollapse: "collapse", width: "100%" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "0.35rem 0.5rem" }}>
                      When
                    </th>
                    <th style={{ textAlign: "left", padding: "0.35rem 0.5rem" }}>
                      Kind
                    </th>
                    <th style={{ textAlign: "left", padding: "0.35rem 0.5rem" }}>
                      Status
                    </th>
                    <th style={{ textAlign: "left", padding: "0.35rem 0.5rem" }}>
                      Error
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr key={j.id}>
                      <td style={{ padding: "0.35rem 0.5rem", fontSize: "0.85rem" }}>
                        {j.finished_at || j.created_at || "—"}
                      </td>
                      <td style={{ padding: "0.35rem 0.5rem" }}>{j.kind}</td>
                      <td style={{ padding: "0.35rem 0.5rem" }}>{j.status}</td>
                      <td
                        style={{
                          padding: "0.35rem 0.5rem",
                          color: j.error ? "#b00020" : "#555",
                          fontSize: "0.85rem",
                        }}
                      >
                        {j.error || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}
