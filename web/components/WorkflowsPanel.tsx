"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { authInputClassName } from "@/components/auth/PublicAuthShell";

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
  const [items, setItems] = useState<WorkflowTemplate[] | null | undefined>(undefined);
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
      const draft = await apiClient.post<WorkflowTemplate>(`/workflows/${id}/copy`, {
        accessToken,
        clientId: tenantId,
        json: {
          owner_slack_user_id: copyOwner.trim() || "U_PORTAL",
          title: undefined,
        },
      });
      if (!draft) {
        throw new Error("Empty copy response");
      }
      setNote(`Copied personal draft “${draft.title}” (${draft.id}). Original unchanged.`);
      await load();
    } catch (err) {
      setNote(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-headline-sm">Workflow library</CardTitle>
          <CardDescription>
            Shared workflow templates stored from Slack. Copy creates a personal draft without
            changing the original. Ask Slack to advise on a template for file-grounded guidance.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <input
              type="search"
              placeholder="Search title / filename"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className={authInputClassName + " max-w-xs"}
            />
            <Button type="button" variant="secondary" className="rounded-full" onClick={() => load()}>
              Refresh
            </Button>
          </div>
          <label className="block text-sm text-muted-foreground">
            Copy owner Slack user id
            <input
              value={copyOwner}
              onChange={(e) => setCopyOwner(e.target.value)}
              className={authInputClassName + " mt-2 max-w-xs"}
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={includePersonal}
              onChange={(e) => setIncludePersonal(e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Include personal drafts for copy owner
          </label>
          {items && items.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              Showing {counts.shared} shared
              {includePersonal ? ` · ${counts.personal} personal draft(s)` : ""}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {error ? (
        <p className="text-body-md text-danger" role="alert">
          {error}
        </p>
      ) : null}
      {note ? (
        <Card className="border-primary/20 bg-primary/5">
          <CardContent className="py-4 text-body-md text-foreground">{note}</CardContent>
        </Card>
      ) : null}
      {items === undefined ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">Loading…</CardContent>
        </Card>
      ) : null}
      {items === null && !error ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Sign in to view workflows.
          </CardContent>
        </Card>
      ) : null}
      {items && items.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No shared templates yet. Store one from Slack with an attachment.
          </CardContent>
        </Card>
      ) : null}
      {items && items.length > 0 ? (
        <div className="space-y-4">
          {items.map((t) => (
            <Card key={t.id}>
              <CardHeader className="flex-row items-start justify-between space-y-0 pb-3">
                <div>
                  <CardTitle className="text-headline-sm">{t.title}</CardTitle>
                  <CardDescription className="mt-1">
                    <Badge variant={t.visibility === "personal" ? "default" : "success"}>
                      {t.visibility === "personal" ? "personal draft" : "shared"}
                    </Badge>
                  </CardDescription>
                </div>
                {t.visibility === "shared" ? (
                  <Button
                    type="button"
                    size="sm"
                    className="rounded-full"
                    disabled={busyId === t.id}
                    onClick={() => copyTemplate(t.id)}
                  >
                    {busyId === t.id ? "Copying…" : "Copy to my draft"}
                  </Button>
                ) : null}
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <code className="block text-xs text-foreground">{t.id}</code>
                <p>
                  {t.original_filename}
                  {t.parent_id ? ` · copy of ${t.parent_id} (original unchanged)` : ""} · v
                  {t.version}
                  {t.owner_slack_user_id ? ` · owner ${t.owner_slack_user_id}` : ""}
                </p>
                {t.body_text_preview ? (
                  <p>
                    Preview: {t.body_text_preview.slice(0, 160)}
                    {t.body_text_preview.length > 160 ? "…" : ""}
                  </p>
                ) : null}
                {t.visibility === "personal" ? (
                  <p className="text-success">Personal draft ready to edit in Slack</p>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}
    </div>
  );
}
