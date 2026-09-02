"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Play, Sparkles } from "lucide-react";
import { ApiError, apiClient } from "@/lib/api";
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
};

type TenantSummary = {
  id: string;
  name: string;
  slug: string;
};

type PlanStep = {
  tool_name?: string;
  step_type?: string;
  arguments?: Record<string, unknown>;
  success_criteria?: string;
  advice?: string;
  message?: string;
  [key: string]: unknown;
};

type ExecutedStep = {
  step_index: number;
  tool_name: string | null;
  arguments: Record<string, unknown> | null;
  success_criteria: string | null;
  status: string;
  result: unknown;
  error: string | null;
};

type TraceResponse = {
  tenant_id: string;
  tenant_name?: string | null;
  question: string;
  status: string;
  phase?: string;
  workflow: string;
  plan_id?: string | null;
  run_id?: string | null;
  orchestrator_system_prompt?: string | null;
  orchestrator_user_prompt?: string | null;
  plan_steps: PlanStep[];
  executed_steps: ExecutedStep[];
  planner_model?: string | null;
  final_answer: string;
  llm?: {
    llm_provider: string;
    orchestrator_model: string;
    executor_model: string;
    orchestrator_model_tier: string;
    executor_model_tier: string;
  };
};

const inputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

const traceBlockClassName =
  "mt-2 max-h-[28rem] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border bg-[#f8fafc] p-4 font-mono text-[0.78rem] leading-relaxed text-foreground";

function pretty(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function statusVariant(status: string): "success" | "warning" | "danger" | "muted" {
  const value = status.trim().toLowerCase();
  if (value === "completed" || value === "success" || value === "succeeded") {
    return "success";
  }
  if (value === "failed" || value === "error") return "danger";
  if (value === "running" || value === "pending") return "warning";
  return "muted";
}

export function AgentTracePanel({ accessToken }: Props) {
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [question, setQuestion] = useState("");
  const [loadingTenants, setLoadingTenants] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [trace, setTrace] = useState<TraceResponse | null>(null);

  const loadTenants = useCallback(async () => {
    if (!accessToken) {
      setLoadingTenants(false);
      setError("Sign in as platform owner to use this page.");
      return;
    }
    setLoadingTenants(true);
    setError(null);
    try {
      const data = await apiClient.get<{ tenants: TenantSummary[] }>(
        "/admin/tenants",
        { accessToken, clientId: null },
      );
      const list = data?.tenants ?? [];
      setTenants(list);
      setTenantId((current) => current || (list[0]?.id ?? ""));
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to load tenants";
      setError(message);
    } finally {
      setLoadingTenants(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void loadTenants();
  }, [loadTenants]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!accessToken) {
      setError("Sign in as platform owner to use this page.");
      return;
    }
    if (!tenantId.trim()) {
      setError("Select a tenant.");
      return;
    }
    if (!question.trim()) {
      setError("Enter a request.");
      return;
    }
    setRunning(true);
    setError(null);
    setTrace(null);
    try {
      const data = await apiClient.post<TraceResponse>("/admin/agent-trace", {
        accessToken,
        clientId: tenantId,
        json: { tenant_id: tenantId, question: question.trim() },
      });
      if (!data) {
        setError("Empty response from agent-trace");
        return;
      }
      setTrace(data);
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Agent trace failed";
      setError(message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
              <Sparkles className="h-5 w-5" />
            </span>
            <div>
              <CardTitle className="text-headline-md">Request</CardTitle>
              <CardDescription className="mt-1">
                Runs orchestrator → executor for the selected tenant and shows prompts, plan
                steps, and the final answer.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5 pt-6">
          <form onSubmit={onSubmit} className="space-y-4">
            <label className="block max-w-md">
              <span className="text-sm font-medium text-foreground">Tenant</span>
              <select
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                disabled={loadingTenants || running}
                required
                className={cn(inputClassName, "mt-2")}
              >
                {tenants.length === 0 ? (
                  <option value="">No tenants</option>
                ) : (
                  tenants.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.slug})
                    </option>
                  ))
                )}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-foreground">Request</span>
              <textarea
                rows={4}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="e.g. Summarize our onboarding docs"
                disabled={running}
                required
                className={cn(inputClassName, "mt-2 min-h-[6rem] resize-y")}
              />
            </label>
            <Button
              type="submit"
              className="rounded-full"
              disabled={running || loadingTenants || !tenantId}
            >
              <Play className="h-4 w-4" />
              {running ? "Running…" : "Run agent trace"}
            </Button>
          </form>
          {error ? (
            <p className="text-sm text-danger" role="alert">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {trace ? (
        <div className="space-y-6">
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">Run summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-6 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">Status</span>
                <Badge variant={statusVariant(trace.status)} className="capitalize">
                  {trace.status}
                </Badge>
                {trace.phase ? (
                  <Badge variant="muted">phase {trace.phase}</Badge>
                ) : null}
                {trace.workflow ? (
                  <Badge variant="muted">workflow {trace.workflow}</Badge>
                ) : null}
              </div>
              {trace.planner_model ? (
                <p className="text-muted-foreground">Planner model: {trace.planner_model}</p>
              ) : null}
              {trace.llm ? (
                <p className="text-muted-foreground">
                  Provider {trace.llm.llm_provider} · orchestrator {trace.llm.orchestrator_model}{" "}
                  ({trace.llm.orchestrator_model_tier}) · executor {trace.llm.executor_model} (
                  {trace.llm.executor_model_tier})
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">Orchestrator system prompt</CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <pre className={traceBlockClassName}>
                {trace.orchestrator_system_prompt || "(none)"}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">Orchestrator user prompt</CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <pre className={traceBlockClassName}>
                {trace.orchestrator_user_prompt || "(none)"}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">
                Plan steps (from planner LLM → executor)
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              {trace.plan_steps?.length ? (
                <pre className={traceBlockClassName}>{pretty(trace.plan_steps)}</pre>
              ) : (
                <p className="text-body-md text-muted-foreground">No plan steps returned.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">Executed steps</CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              {trace.executed_steps?.length ? (
                <pre className={traceBlockClassName}>{pretty(trace.executed_steps)}</pre>
              ) : (
                <p className="text-body-md text-muted-foreground">No executed steps stored.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle className="text-headline-md">Final answer (executor)</CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <pre className={traceBlockClassName}>{trace.final_answer || "(empty)"}</pre>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
