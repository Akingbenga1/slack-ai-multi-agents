"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
};

type WorkflowTemplate = {
  id: string;
  title: string;
  visibility: string;
  original_filename: string;
  parent_id?: string | null;
  version: number;
  owner_slack_user_id?: string | null;
  updated_at?: string | null;
  body_text_preview?: string | null;
};

export function WorkflowsPanel({ accessToken, tenantId }: Props) {
  const [items, setItems] = useState<WorkflowTemplate[] | null | undefined>(
    undefined,
  );
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [copyOwner, setCopyOwner] = useState("U_PORTAL");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [includePersonal, setIncludePersonal] = useState(true);

  const load = useCallback(async () => {
    if (!accessToken) {
      setItems(null);
      return;
    }
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (includePersonal && copyOwner.trim()) {
      params.set("include_personal_for", copyOwner.trim());
    }
    const qs = params.toString();
    const body = await apiClient.get<{ templates: WorkflowTemplate[] }>(
      `/workflows${qs ? `?${qs}` : ""}`,
      { accessToken, clientId: tenantId },
    );
    setItems(body?.templates || []);
  }, [accessToken, tenantId, q, includePersonal, copyOwner]);

  useEffect(() => {
    let cancelled = false;
    setItems(undefined);
    setError(null);
    load().catch((err) => {
      if (!cancelled) {
        setItems(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const counts = useMemo(() => {
    const list = items || [];
    return {
      shared: list.filter((t) => t.visibility === "shared").length,
      personal: list.filter((t) => t.visibility === "personal").length,
    };
  }, [items]);

  async function copyTemplate(id: string) {
    if (!accessToken) return;
    setBusyId(id);
    setNote(null);
    try {
      const draft = await apiClient.post<WorkflowTemplate>(
        `/workflows/${id}/copy`,
        {
          accessToken,
          clientId: tenantId,
          json: {
            owner_slack_user_id: copyOwner.trim() || "U_PORTAL",
            title: undefined,
          },
        },
      );
      if (!draft) {
        throw new Error("Empty copy response");
      }
      setNote(
        `Copied personal draft “${draft.title}” (${draft.id}). Original unchanged.`,
      );
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section style={{ display: "grid", gap: "0.75rem" }}>
      <p style={{ margin: 0, color: "#444", fontSize: "0.95rem" }}>
        Shared workflow templates stored from Slack (TM-20 / TM-21). Copy creates
        a personal draft without changing the original. Ask Slack to advise on a
        template for file-grounded guidance (TM-22).
      </p>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        <input
          type="search"
          placeholder="Search title / filename"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ minWidth: 200, padding: "0.35rem 0.5rem" }}
        />
        <button type="button" onClick={() => load()}>
          Refresh
        </button>
      </div>
      <label style={{ fontSize: "0.9rem" }}>
        Copy owner Slack user id{" "}
        <input
          value={copyOwner}
          onChange={(e) => setCopyOwner(e.target.value)}
          style={{ marginLeft: "0.35rem", padding: "0.25rem 0.4rem" }}
        />
      </label>
      <label style={{ fontSize: "0.9rem" }}>
        <input
          type="checkbox"
          checked={includePersonal}
          onChange={(e) => setIncludePersonal(e.target.checked)}
          style={{ marginRight: "0.35rem" }}
        />
        Include personal drafts for copy owner
      </label>
      {items && items.length > 0 ? (
        <p style={{ margin: 0, fontSize: "0.9rem", color: "#555" }}>
          Showing {counts.shared} shared
          {includePersonal ? ` · ${counts.personal} personal draft(s)` : ""}
        </p>
      ) : null}
      {error ? <p style={{ color: "#b00020" }}>{error}</p> : null}
      {note ? <p style={{ color: "#0a5" }}>{note}</p> : null}
      {items === undefined ? <p>Loading…</p> : null}
      {items === null && !error ? <p>Sign in to view workflows.</p> : null}
      {items && items.length === 0 ? (
        <p>No shared templates yet. Store one from Slack with an attachment.</p>
      ) : null}
      {items && items.length > 0 ? (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {items.map((t) => (
            <li
              key={t.id}
              style={{
                padding: "0.65rem 0",
                borderBottom: "1px solid #eee",
                display: "grid",
                gap: "0.25rem",
              }}
            >
              <strong>
                {t.title}{" "}
                <span style={{ fontWeight: 400, color: "#666" }}>
                  ({t.visibility === "personal" ? "personal draft" : "shared"})
                </span>
              </strong>
              <code style={{ fontSize: "0.8rem" }}>{t.id}</code>
              <span style={{ fontSize: "0.9rem", color: "#444" }}>
                {t.original_filename}
                {t.parent_id
                  ? ` · copy of ${t.parent_id} (original unchanged)`
                  : ""}{" "}
                · v{t.version}
                {t.owner_slack_user_id
                  ? ` · owner ${t.owner_slack_user_id}`
                  : ""}
              </span>
              {t.body_text_preview ? (
                <span style={{ fontSize: "0.85rem", color: "#666" }}>
                  Preview: {t.body_text_preview.slice(0, 160)}
                  {t.body_text_preview.length > 160 ? "…" : ""}
                </span>
              ) : null}
              {t.visibility === "shared" ? (
                <button
                  type="button"
                  disabled={busyId === t.id}
                  onClick={() => copyTemplate(t.id)}
                  style={{ width: "fit-content" }}
                >
                  {busyId === t.id ? "Copying…" : "Copy to my draft"}
                </button>
              ) : (
                <span style={{ fontSize: "0.85rem", color: "#0a5" }}>
                  Copy status: personal draft ready to edit in Slack
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
