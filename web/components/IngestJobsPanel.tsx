"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

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

function jobStatusVariant(
  status: string,
): "success" | "warning" | "danger" | "muted" {
  const value = status.trim().toLowerCase();
  if (value === "succeeded" || value === "success" || value === "completed") {
    return "success";
  }
  if (value === "failed" || value === "error") {
    return "danger";
  }
  if (value === "running" || value === "pending" || value === "queued") {
    return "warning";
  }
  return "muted";
}

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function IngestJobsPanel({
  accessToken,
  tenantId,
  refreshKey = 0,
}: Props) {
  const [jobs, setJobs] = useState<IngestJob[] | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) {
      setJobs(null);
      return;
    }
    const body = await apiClient.get<{ jobs: IngestJob[] }>(
      "/uploads/jobs?limit=20",
      { accessToken, clientId: tenantId },
    );
    setJobs(body?.jobs || []);
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

  const jobCount = jobs?.length ?? 0;

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-5">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-headline-md text-foreground">Ingest jobs</h2>
            {jobs && jobs.length > 0 ? (
              <Badge variant="muted">{jobCount}</Badge>
            ) : null}
          </div>
          <p className="mt-1 text-body-md text-muted-foreground">
            Recent document and Slack history ingest tasks for this organisation.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => load().catch((err) => setError(String(err)))}
          disabled={!accessToken}
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <CardContent className="px-0 pb-0 pt-0">
        {error ? (
          <p className="px-6 py-4 text-body-md text-danger" role="alert">
            {error}
          </p>
        ) : null}

        {jobs === undefined ? (
          <div className="space-y-2 px-6 py-6">
            {[0, 1, 2].map((key) => (
              <div key={key} className="h-10 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : jobs === null || jobs.length === 0 ? (
          <p className="px-6 py-8 text-center text-body-md text-muted-foreground">
            No ingest jobs yet. Upload a document or Slack history export above.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-[#f8fafc]">
                  <th
                    scope="col"
                    className="px-6 py-3 text-label-md text-muted-foreground"
                  >
                    Status
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-label-md text-muted-foreground"
                  >
                    File
                  </th>
                  <th
                    scope="col"
                    className="px-4 py-3 text-label-md text-muted-foreground"
                  >
                    Role
                  </th>
                  <th
                    scope="col"
                    className="px-6 py-3 text-label-md text-muted-foreground"
                  >
                    Created
                  </th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr
                    key={job.job_id}
                    className="border-b border-border last:border-b-0 hover:bg-muted/40"
                  >
                    <td className="px-6 py-3">
                      <Badge
                        variant={jobStatusVariant(job.status)}
                        className="capitalize"
                      >
                        {job.status}
                      </Badge>
                      {job.error ? (
                        <p className="mt-1 max-w-xs text-xs text-danger">
                          {job.error}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {job.filename || "—"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {job.file_role || "—"}
                    </td>
                    <td className="px-6 py-3 text-muted-foreground">
                      {formatWhen(job.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
