"use client";

import { useCallback, useEffect, useState } from "react";
import { apiAuthHeaders, getApiBaseUrl } from "@/lib/api";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
  /** Bump to force refresh after upload */
  refreshKey?: number;
};

type IngestJob = {
  job_id: string;
  status: string;
  upload_id?: string | null;
  filename?: string | null;
  file_role?: string | null;
  error?: string | null;
  created_at?: string | null;
  finished_at?: string | null;
};

export function IngestJobsPanel({ accessToken, tenantId, refreshKey = 0 }: Props) {
  const [jobs, setJobs] = useState<IngestJob[] | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) {
      setJobs(null);
      return;
    }
    const res = await fetch(`${getApiBaseUrl()}/uploads/jobs?limit=20`, {
      headers: apiAuthHeaders(accessToken, tenantId),
    });
    if (!res.ok) {
      throw new Error((await res.text()) || res.statusText);
    }
    const body = (await res.json()) as { jobs: IngestJob[] };
    setJobs(body.jobs || []);
  }, [accessToken, tenantId]);

  useEffect(() => {
    let cancelled = false;
    setJobs(undefined);
    setError(null);
    load().catch((err) => {
      if (!cancelled) {
        setJobs(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [load, refreshKey]);

  return (
    <section style={{ display: "grid", gap: "0.75rem" }}>
      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Ingest status</h2>
        <button
          type="button"
          onClick={() => load().catch((err) => setError(String(err)))}
          disabled={!accessToken}
          style={{ padding: "0.35rem 0.6rem" }}
        >
          Refresh
        </button>
      </div>
      {error ? (
        <p style={{ color: "#b00020", margin: 0 }} role="alert">
          {error}
        </p>
      ) : null}
      {jobs === undefined ? (
        <p style={{ margin: 0 }}>Loading ingest jobs…</p>
      ) : jobs === null || jobs.length === 0 ? (
        <p style={{ margin: 0, color: "#555" }}>
          No ingest jobs yet. Upload a document or Slack history dump above.
        </p>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%", maxWidth: 720 }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left", padding: "0.35rem" }}>Status</th>
              <th style={{ textAlign: "left", padding: "0.35rem" }}>File</th>
              <th style={{ textAlign: "left", padding: "0.35rem" }}>Role</th>
              <th style={{ textAlign: "left", padding: "0.35rem" }}>Created</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j) => (
              <tr key={j.job_id}>
                <td style={{ padding: "0.35rem" }}>
                  {j.status}
                  {j.error ? (
                    <span style={{ color: "#b00020", display: "block", fontSize: "0.8rem" }}>
                      {j.error}
                    </span>
                  ) : null}
                </td>
                <td style={{ padding: "0.35rem" }}>{j.filename || "—"}</td>
                <td style={{ padding: "0.35rem" }}>{j.file_role || "—"}</td>
                <td style={{ padding: "0.35rem", fontSize: "0.85rem" }}>
                  {j.created_at || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
