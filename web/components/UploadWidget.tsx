"use client";

import { FormEvent, useState } from "react";
import { CheckCircle2, Upload } from "lucide-react";
import { apiAuthHeaders, getApiBaseUrl } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type FileRole = "document" | "slack_history";

type UploadOk = {
  upload_id: string;
  client_id: string;
  file_role: string;
  filename: string;
  relative_path: string;
  size_bytes: number;
  status: string;
  task_id?: string | null;
  queue?: string | null;
};

type Props = {
  accessToken: string | null;
  tenantId: string | null;
  onUploaded?: (result: UploadOk) => void;
};

const ACCEPT_BY_ROLE: Record<FileRole, string> = {
  document: ".pdf,.docx,.xlsx,.csv",
  slack_history: ".zip,.json,.ndjson,.csv,.xlsx",
};

const ROLE_LABELS: Record<FileRole, string> = {
  document: "Document (PDF, DOCX, XLSX, CSV)",
  slack_history: "Slack history (ZIP, JSON, NDJSON, CSV, XLSX)",
};

const inputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

export function UploadWidget({ accessToken, tenantId, onUploaded }: Props) {
  const [fileRole, setFileRole] = useState<FileRole>("document");
  const [file, setFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UploadOk | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!accessToken) {
      setError(
        "No API token in session. Start the API, seed demo users, then sign out and sign in again.",
      );
      return;
    }
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }

    setPending(true);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("file_role", fileRole);

      const res = await fetch(`${getApiBaseUrl()}/uploads`, {
        method: "POST",
        headers: apiAuthHeaders(accessToken, tenantId),
        body,
      });

      const text = await res.text();
      let payload: unknown = null;
      try {
        payload = text ? JSON.parse(text) : null;
      } catch {
        payload = text;
      }

      if (!res.ok) {
        const detail =
          typeof payload === "object" &&
          payload !== null &&
          "detail" in payload
            ? String((payload as { detail: unknown }).detail)
            : text || res.statusText;
        setError(`Upload failed (${res.status}): ${detail}`);
        return;
      }

      const ok = payload as UploadOk;
      setResult(ok);
      onUploaded?.(ok);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload request failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card>
      <CardHeader className="border-b border-border">
        <div className="flex flex-wrap items-center gap-3">
          <CardTitle className="text-headline-md">Knowledge upload</CardTitle>
          <Badge variant="muted">POST /uploads</Badge>
        </div>
        <CardDescription>
          Upload documents or Slack history exports. Ingest runs asynchronously via
          Celery after upload.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-6">
        {!accessToken ? (
          <p className="rounded-lg border border-danger/20 bg-danger-muted px-4 py-3 text-body-md text-danger" role="status">
            API JWT missing. Ensure FastAPI is running, demo users are seeded, then
            re-login.
          </p>
        ) : null}

        <form onSubmit={onSubmit} className="grid max-w-xl gap-4">
          <label className="block">
            <span className="text-sm font-medium text-foreground">File role</span>
            <select
              value={fileRole}
              onChange={(e) => {
                setFileRole(e.target.value as FileRole);
                setFile(null);
              }}
              className={cn(inputClassName, "mt-2")}
            >
              {(Object.keys(ROLE_LABELS) as FileRole[]).map((role) => (
                <option key={role} value={role}>
                  {ROLE_LABELS[role]}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-foreground">File</span>
            <input
              key={fileRole}
              type="file"
              accept={ACCEPT_BY_ROLE[fileRole]}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
              className={cn(
                inputClassName,
                "mt-2 file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-sm file:font-medium",
              )}
            />
          </label>

          <Button
            type="submit"
            disabled={pending || !accessToken}
            className="w-fit rounded-full"
          >
            <Upload className="h-4 w-4" />
            {pending ? "Uploading…" : "Upload file"}
          </Button>
        </form>

        {error ? (
          <p className="text-body-md text-danger" role="alert">
            {error}
          </p>
        ) : null}

        {result ? (
          <div
            className="flex items-start gap-3 rounded-lg border border-success/20 bg-success-muted px-4 py-3 text-body-md text-success"
            role="status"
          >
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Upload accepted</p>
              <p className="mt-1 text-sm opacity-90">
                {result.filename} · {result.status}
                {result.task_id ? ` · task ${result.task_id}` : ""}
              </p>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
