"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
  /** Bump to force refresh after upload */
  refreshKey?: number;
};

type TenantFile = {
  relative_path: string;
  filename: string;
  size_bytes: number;
  modified_at: string;
};

type TenantFileListResponse = {
  client_id: string;
  files: TenantFile[];
  truncated: boolean;
  next_cursor?: string | null;
};

function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function buildDownloadHref(file: TenantFile, tenantId: string | null): string {
  const params = new URLSearchParams({
    key: file.relative_path,
    filename: file.filename,
  });
  if (tenantId) {
    params.set("tenantId", tenantId);
  }
  return `/api/tenant-files/download?${params.toString()}`;
}

export function TenantFilesPanel({
  accessToken,
  tenantId,
  refreshKey = 0,
}: Props) {
  const [files, setFiles] = useState<TenantFile[] | null | undefined>(undefined);
  const [truncated, setTruncated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!accessToken) {
      setFiles(null);
      setTruncated(false);
      return;
    }
    const body = await apiClient.get<TenantFileListResponse>(
      "/tenant-files?limit=500",
      { accessToken, clientId: tenantId },
    );
    setFiles(body?.files || []);
    setTruncated(Boolean(body?.truncated));
  }, [accessToken, tenantId]);

  useEffect(() => {
    let cancelled = false;
    setFiles(undefined);
    setError(null);
    load().catch((err) => {
      if (!cancelled) {
        setFiles(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [load, refreshKey]);

  const fileCount = files?.length ?? 0;

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-5">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-headline-md text-foreground">Tenant files</h2>
            {files && files.length > 0 ? (
              <Badge variant="muted">{fileCount}</Badge>
            ) : null}
          </div>
          <p className="mt-1 text-body-md text-muted-foreground">
            Files stored on disk for this organisation.
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

        {files === undefined ? (
          <div className="space-y-2 px-6 py-6">
            {[0, 1, 2].map((key) => (
              <div key={key} className="h-10 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : files === null || files.length === 0 ? (
          <p className="px-6 py-8 text-center text-body-md text-muted-foreground">
            No files stored for this tenant yet.
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border bg-[#f8fafc]">
                    <th
                      scope="col"
                      className="px-6 py-3 text-label-md text-muted-foreground"
                    >
                      File
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-label-md text-muted-foreground"
                    >
                      Modified
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-3 text-right text-label-md text-muted-foreground"
                    >
                      Download
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => (
                    <tr
                      key={file.relative_path}
                      className="border-b border-border last:border-b-0 hover:bg-muted/40"
                    >
                      <td className="px-6 py-3 text-foreground">
                        {file.filename}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatWhen(file.modified_at)}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <a
                          href={buildDownloadHref(file, tenantId)}
                          download={file.filename}
                          className={cn(
                            buttonVariants({ variant: "outline", size: "sm" }),
                          )}
                          aria-label={`Download ${file.filename}`}
                        >
                          Download
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {truncated ? (
              <p className="px-6 py-4 text-sm text-muted-foreground">
                Showing the first 500 files. More exist on disk.
              </p>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
