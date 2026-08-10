"use client";

import { FormEvent, useState } from "react";
import { apiAuthHeaders, getApiBaseUrl } from "@/lib/api";

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
        "No API token in session. Start the API (and seed demo users), then sign out and sign in again.",
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
      // Tenant from JWT / X-Client-Id only — do not append form tenant_id
      // (avoids browser spoofing of a foreign org).

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
    <section
      style={{
        maxWidth: 480,
        display: "grid",
        gap: "0.75rem",
      }}
    >
      <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Knowledge upload</h2>
      <p style={{ margin: 0, color: "#555", fontSize: "0.9rem" }}>
        Upload documents or Slack history dumps. Ingest runs via Celery (
        <code>POST /uploads</code>).
      </p>

      {!accessToken ? (
        <p style={{ color: "#b00020", margin: 0 }} role="status">
          API JWT missing. Ensure FastAPI is up, demo users are seeded, then
          re-login as org admin.
        </p>
      ) : null}

      <form onSubmit={onSubmit} style={{ display: "grid", gap: "0.75rem" }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span>File role</span>
          <select
            value={fileRole}
            onChange={(e) => {
              setFileRole(e.target.value as FileRole);
              setFile(null);
            }}
            style={{ padding: "0.5rem" }}
          >
            <option value="document">document (PDF, DOCX, XLSX, CSV)</option>
            <option value="slack_history">
              slack_history (ZIP, JSON, NDJSON, CSV, XLSX)
            </option>
          </select>
        </label>

        <label style={{ display: "grid", gap: 4 }}>
          <span>File</span>
          <input
            key={fileRole}
            type="file"
            accept={ACCEPT_BY_ROLE[fileRole]}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
          />
        </label>

        <button
          type="submit"
          disabled={pending || !accessToken}
          style={{ padding: "0.6rem", width: "fit-content" }}
        >
          {pending ? "Uploading…" : "Upload"}
        </button>
      </form>

      {error ? (
        <p style={{ color: "#b00020", margin: 0 }} role="alert">
          {error}
        </p>
      ) : null}

      {result ? (
        <div
          style={{
            margin: 0,
            padding: "0.75rem",
            background: "#f4f6f8",
            border: "1px solid #d0d7de",
            fontSize: "0.85rem",
          }}
          role="status"
        >
          <strong>Upload OK</strong> — {result.filename} ({result.status}
          {result.task_id ? `, task ${result.task_id}` : ""})
        </div>
      ) : null}
    </section>
  );
}
