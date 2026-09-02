"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Bot,
  Clock,
  Info,
  Lock,
  RefreshCw,
  Save,
  Shield,
} from "lucide-react";
import { apiClient } from "@/lib/api";
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

type Props = {
  accessToken: string | null;
  tenantId: string | null;
};

type Allowlist = { channels: string[] };

type AgentConfig = {
  client_id: string;
  config_id: string;
  name: string;
  system_prompt: string | null;
  allowlist: Allowlist | null;
  schedules: {
    slack_history_sync?: { enabled: boolean };
    recurring_report?: {
      enabled: boolean;
      channel_id: string | null;
      cadence: string;
      window_label: string;
    };
  };
  updated_at: string | null;
};

const inputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

const monoInputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 font-mono text-[13px] text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

async function loadConfig(
  accessToken: string,
  tenantId: string | null,
): Promise<AgentConfig> {
  const cfg = await apiClient.get<AgentConfig>("/agent/config", {
    accessToken,
    clientId: tenantId,
  });
  if (!cfg) {
    throw new Error("Empty agent config response");
  }
  return cfg;
}

function applyConfig(cfg: AgentConfig) {
  return {
    name: cfg.name || "",
    prompt: cfg.system_prompt || "",
    channels: cfg.allowlist?.channels || [],
    syncEnabled: cfg.schedules?.slack_history_sync?.enabled ?? true,
    reportEnabled: cfg.schedules?.recurring_report?.enabled ?? false,
    reportChannel: cfg.schedules?.recurring_report?.channel_id || "",
    cadence: cfg.schedules?.recurring_report?.cadence || "weekly",
    windowLabel: cfg.schedules?.recurring_report?.window_label || "last 7 days",
  };
}

function estimateTokens(text: string): number {
  if (!text.trim()) return 0;
  return Math.ceil(text.trim().length / 4);
}

function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {hint ? (
        <span className="mt-1 block text-sm text-muted-foreground">{hint}</span>
      ) : null}
      <div className="mt-2">{children}</div>
    </label>
  );
}

function LoadingSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        {[0, 1].map((key) => (
          <div key={key} className="h-56 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
      <div className="space-y-6">
        {[0, 1].map((key) => (
          <div key={key} className="h-48 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    </div>
  );
}

export function AgentSettingsPanel({ accessToken, tenantId }: Props) {
  const [data, setData] = useState<AgentConfig | null | undefined>(undefined);
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [channels, setChannels] = useState<string[]>([]);
  const [channelDraft, setChannelDraft] = useState("");
  const [syncEnabled, setSyncEnabled] = useState(true);
  const [reportEnabled, setReportEnabled] = useState(false);
  const [reportChannel, setReportChannel] = useState("");
  const [cadence, setCadence] = useState("weekly");
  const [windowLabel, setWindowLabel] = useState("last 7 days");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [pendingIdentity, setPendingIdentity] = useState(false);
  const [pendingSchedules, setPendingSchedules] = useState(false);

  const resetForm = useCallback((cfg: AgentConfig) => {
    const next = applyConfig(cfg);
    setName(next.name);
    setPrompt(next.prompt);
    setChannels(next.channels);
    setChannelDraft("");
    setSyncEnabled(next.syncEnabled);
    setReportEnabled(next.reportEnabled);
    setReportChannel(next.reportChannel);
    setCadence(next.cadence);
    setWindowLabel(next.windowLabel);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setData(undefined);
    setError(null);
    if (!accessToken) {
      setData(null);
      return;
    }
    (async () => {
      try {
        const cfg = await loadConfig(accessToken, tenantId);
        if (cancelled) return;
        setData(cfg);
        resetForm(cfg);
      } catch (err) {
        if (cancelled) return;
        setData(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, tenantId, resetForm]);

  const refresh = useCallback(async () => {
    if (!accessToken) {
      setData(null);
      return;
    }
    setError(null);
    const cfg = await loadConfig(accessToken, tenantId);
    setData(cfg);
    resetForm(cfg);
  }, [accessToken, tenantId, resetForm]);

  function discardChanges() {
    if (data) {
      resetForm(data);
      setSaved(null);
      setError(null);
    }
  }

  function addChannel() {
    const value = channelDraft.trim();
    if (!value || channels.includes(value)) {
      setChannelDraft("");
      return;
    }
    setChannels((prev) => [...prev, value]);
    setChannelDraft("");
  }

  function removeChannel(channelId: string) {
    setChannels((prev) => prev.filter((id) => id !== channelId));
  }

  async function onSaveIdentity(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setPendingIdentity(true);
    setError(null);
    setSaved(null);
    try {
      await apiClient.patch("/agent/config", {
        accessToken,
        clientId: tenantId,
        json: {
          name,
          system_prompt: prompt,
          allowlist: { channels },
        },
      });
      setSaved("Agent details saved.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPendingIdentity(false);
    }
  }

  async function onSaveSchedules(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) return;
    setPendingSchedules(true);
    setError(null);
    setSaved(null);
    try {
      const reportBody: Record<string, unknown> = {
        enabled: reportEnabled,
        cadence,
        window_label: windowLabel,
      };
      if (reportChannel.trim()) {
        reportBody.channel_id = reportChannel.trim();
      } else {
        reportBody.clear_channel = true;
      }
      await apiClient.patch("/agent/schedules", {
        accessToken,
        clientId: tenantId,
        json: {
          slack_history_sync: { enabled: syncEnabled },
          recurring_report: reportBody,
        },
      });
      setSaved("Schedules saved.");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setPendingSchedules(false);
    }
  }

  const tokenEstimate = useMemo(() => estimateTokens(prompt), [prompt]);
  const pending = pendingIdentity || pendingSchedules;

  if (!accessToken) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <p className="text-body-md text-danger" role="status">
            API JWT missing. Start FastAPI, seed demo users, then re-login.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (data === undefined) {
    return <LoadingSkeleton />;
  }

  if (data === null && error) {
    return (
      <Card>
        <CardContent className="py-10 text-center">
          <p className="text-body-md text-danger" role="alert">
            {error}
          </p>
          <Button
            type="button"
            variant="outline"
            className="mt-4"
            onClick={() => void refresh()}
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant="success" className="gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
              Active
            </Badge>
            {data?.config_id ? (
              <span className="font-mono text-[13px] text-muted-foreground">
                Config {data.config_id}
              </span>
            ) : null}
          </div>
          <h2 className="mt-3 text-headline-md text-foreground">
            {name.trim() || "Agent settings"}
          </h2>
          {data?.updated_at ? (
            <p className="mt-1 text-sm text-muted-foreground">
              Last updated {data.updated_at}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={pending || !data}
            onClick={discardChanges}
          >
            Discard
          </Button>
          <Button
            type="submit"
            form="agent-identity-form"
            disabled={pendingIdentity}
          >
            <Save className="h-4 w-4" />
            {pendingIdentity ? "Saving…" : "Save agent details"}
          </Button>
        </div>
      </div>

      {error ? (
        <p
          className="rounded-lg border border-danger/30 bg-danger-muted px-4 py-3 text-body-md text-danger"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      {saved ? (
        <p
          className="rounded-lg border border-primary/30 bg-[#ecfdf5] px-4 py-3 text-body-md text-[#006c49]"
          role="status"
        >
          {saved}
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                  <Bot size={20} />
                </span>
                <div>
                  <CardTitle>Agent identity</CardTitle>
                  <CardDescription>
                    Display name shown in Slack and the org portal for this tenant&apos;s agent.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <form id="agent-identity-form" onSubmit={onSaveIdentity} className="space-y-4">
                <FormField label="Agent name">
                  <input
                    className={inputClassName}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </FormField>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                    <Info size={20} />
                  </span>
                  <div>
                    <CardTitle>System prompt</CardTitle>
                    <CardDescription>
                      Optional org overlay prepended to workflow prompts for this tenant.
                    </CardDescription>
                  </div>
                </div>
                <span className="shrink-0 text-sm text-muted-foreground">
                  ~{tokenEstimate} tokens
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <textarea
                className={cn(monoInputClassName, "min-h-[220px] resize-y leading-relaxed")}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={10}
                placeholder="Optional instructions prepended to workflow prompts"
                spellCheck={false}
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                  <Shield size={20} />
                </span>
                <div>
                  <CardTitle>Channel allowlist</CardTitle>
                  <CardDescription>
                    Restrict which Slack channels this agent may respond in. Empty = no restriction
                    stored.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {channels.length > 0 ? (
                  channels.map((channelId) => (
                    <Badge
                      key={channelId}
                      variant="muted"
                      className="gap-1.5 py-1 pl-2.5 pr-1 font-mono text-[13px]"
                    >
                      {channelId}
                      <button
                        type="button"
                        className="rounded px-1 text-muted-foreground hover:bg-background hover:text-foreground"
                        aria-label={`Remove ${channelId}`}
                        onClick={() => removeChannel(channelId)}
                      >
                        ×
                      </button>
                    </Badge>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">No channels restricted.</p>
                )}
              </div>
              <div className="flex gap-2">
                <input
                  className={monoInputClassName}
                  value={channelDraft}
                  onChange={(e) => setChannelDraft(e.target.value)}
                  placeholder="C01234567"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addChannel();
                    }
                  }}
                />
                <Button type="button" variant="outline" onClick={addChannel}>
                  Add
                </Button>
              </div>
              <p className="text-sm text-muted-foreground">
                Enforcement in the Slack reply path can tighten later; settings are tenant-scoped
                today.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                  <Clock size={20} />
                </span>
                <div>
                  <CardTitle>Jobs &amp; schedules</CardTitle>
                  <CardDescription>
                    Background sync and recurring report jobs for this tenant.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <form id="agent-schedules-form" onSubmit={onSaveSchedules} className="space-y-4">
                <label className="flex items-start gap-3 rounded-lg border border-border px-4 py-3">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={syncEnabled}
                    onChange={(e) => setSyncEnabled(e.target.checked)}
                  />
                  <span>
                    <span className="block text-sm font-medium text-foreground">
                      Slack history sync
                    </span>
                    <span className="mt-0.5 block text-sm text-muted-foreground">
                      Enable hourly Slack history sync (Beat).
                    </span>
                  </span>
                </label>

                <label className="flex items-start gap-3 rounded-lg border border-border px-4 py-3">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={reportEnabled}
                    onChange={(e) => setReportEnabled(e.target.checked)}
                  />
                  <span>
                    <span className="block text-sm font-medium text-foreground">
                      Recurring report
                    </span>
                    <span className="mt-0.5 block text-sm text-muted-foreground">
                      Post scheduled summary reports to a Slack channel.
                    </span>
                  </span>
                </label>

                <FormField label="Report channel id">
                  <input
                    className={monoInputClassName}
                    value={reportChannel}
                    onChange={(e) => setReportChannel(e.target.value)}
                    placeholder="C0REPORT"
                  />
                </FormField>

                <FormField label="Cadence">
                  <select
                    className={inputClassName}
                    value={cadence}
                    onChange={(e) => setCadence(e.target.value)}
                  >
                    <option value="weekly">weekly</option>
                    <option value="daily">daily</option>
                  </select>
                </FormField>

                <FormField label="Window label">
                  <input
                    className={inputClassName}
                    value={windowLabel}
                    onChange={(e) => setWindowLabel(e.target.value)}
                  />
                </FormField>

                <Button type="submit" disabled={pendingSchedules} className="w-full">
                  <Lock className="h-4 w-4" />
                  {pendingSchedules ? "Saving…" : "Save schedules"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
