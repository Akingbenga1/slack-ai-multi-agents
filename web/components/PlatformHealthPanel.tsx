"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";

type Props = {
  accessToken: string | null;
};

type HealthPayload = {
  status: string;
  checks?: Record<string, { status: string; detail?: string }>;
  errors?: {
    window_hours: number;
    jobs_total: number;
    jobs_failed: number;
    failure_rate: number;
    failed_by_kind?: { kind: string; count: number }[];
  };
  usage?: {
    by_type?: { event_type: string; count: number }[];
  };
};

export function PlatformHealthPanel({ accessToken }: Props) {
  const [data, setData] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!accessToken) {
      setError("Not signed in");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload = await apiClient.get<HealthPayload>(
        "/admin/health?hours=24",
        { accessToken, clientId: null },
      );
      setData(payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section>
      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Platform health</h2>
        <button type="button" onClick={() => void load()} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>
      {error ? (
        <p style={{ color: "#b00020" }} role="alert">
          {error}
        </p>
      ) : null}
      {data ? (
        <>
          <p>
            Overall: <strong>{data.status}</strong>
          </p>
          <h3>Compose services</h3>
          <ul>
            {Object.entries(data.checks || {}).map(([name, check]) => (
              <li key={name}>
                {name}: {check.status}
                {check.detail ? ` — ${check.detail}` : ""}
              </li>
            ))}
          </ul>
          <h3>Job errors (last {data.errors?.window_hours ?? 24}h)</h3>
          <p>
            Failed {data.errors?.jobs_failed ?? 0} / {data.errors?.jobs_total ?? 0}{" "}
            (
            {((data.errors?.failure_rate ?? 0) * 100).toFixed(1)}%)
          </p>
          {(data.errors?.failed_by_kind || []).length > 0 ? (
            <ul>
              {data.errors!.failed_by_kind!.map((row) => (
                <li key={row.kind}>
                  {row.kind}: {row.count}
                </li>
              ))}
            </ul>
          ) : (
            <p>No failed jobs in window.</p>
          )}
          <h3>Usage events</h3>
          {(data.usage?.by_type || []).length > 0 ? (
            <ul>
              {data.usage!.by_type!.map((row) => (
                <li key={row.event_type}>
                  {row.event_type}: {row.count}
                </li>
              ))}
            </ul>
          ) : (
            <p>No usage events in window.</p>
          )}
        </>
      ) : null}
    </section>
  );
}
