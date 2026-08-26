"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import panel from "@/components/dashboard/panel.module.css";
import { ApiError, apiClient } from "@/lib/api";
import styles from "./AgentTracePanel.module.css";

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

function pretty(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
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
    <div className={panel.grid}>
      <section className={panel.section}>
        <h2 className={panel.sectionTitle}>Request</h2>
        <p className={panel.meta}>
          Runs orchestrator → executor for the selected tenant and shows prompts,
          plan steps, and the final answer.
        </p>
        <form className={panel.formGrid} onSubmit={onSubmit}>
          <label className={panel.formLabel}>
            Tenant
            <select
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              disabled={loadingTenants || running}
              required
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
          <label className={panel.formLabel}>
            Request
            <textarea
              rows={4}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Summarize our onboarding docs"
              disabled={running}
              required
            />
          </label>
          <div className={panel.formRow}>
            <button
              type="submit"
              className={panel.btnPrimary}
              disabled={running || loadingTenants || !tenantId}
            >
              {running ? "Running…" : "Run agent trace"}
            </button>
          </div>
        </form>
        {error ? <p className={panel.error}>{error}</p> : null}
      </section>

      {trace ? (
        <>
          <section className={panel.section}>
            <h2 className={panel.sectionTitle}>Run summary</h2>
            <p className={panel.meta}>
              Status: {trace.status}
              {trace.phase ? ` · phase ${trace.phase}` : ""}
              {trace.workflow ? ` · workflow ${trace.workflow}` : ""}
              {trace.planner_model ? ` · planner ${trace.planner_model}` : ""}
            </p>
            {trace.llm ? (
              <p className={panel.meta}>
                Provider {trace.llm.llm_provider} · orchestrator{" "}
                {trace.llm.orchestrator_model} ({trace.llm.orchestrator_model_tier})
                · executor {trace.llm.executor_model} (
                {trace.llm.executor_model_tier})
              </p>
            ) : null}
          </section>

          <section className={panel.section}>
            <h2 className={panel.sectionTitle}>Orchestrator system prompt</h2>
            <pre className={styles.traceBlock}>
              {trace.orchestrator_system_prompt || "(none)"}
            </pre>
          </section>

          <section className={panel.section}>
            <h2 className={panel.sectionTitle}>Orchestrator user prompt</h2>
            <pre className={styles.traceBlock}>
              {trace.orchestrator_user_prompt || "(none)"}
            </pre>
          </section>

          <section className={panel.section}>
            <h2 className={panel.sectionTitle}>
              Plan steps (from planner LLM → executor)
            </h2>
            {trace.plan_steps?.length ? (
              <pre className={styles.traceBlock}>{pretty(trace.plan_steps)}</pre>
            ) : (
              <p className={panel.empty}>No plan steps returned.</p>
            )}
          </section>

          <section className={panel.section}>
            <h2 className={panel.sectionTitle}>Executed steps</h2>
            {trace.executed_steps?.length ? (
              <pre className={styles.traceBlock}>{pretty(trace.executed_steps)}</pre>
            ) : (
              <p className={panel.empty}>No executed steps stored.</p>
            )}
          </section>

          <section className={panel.section}>
            <h2 className={panel.sectionTitle}>Final answer (executor)</h2>
            <pre className={styles.traceBlock}>
              {trace.final_answer || "(empty)"}
            </pre>
          </section>
        </>
      ) : null}
    </div>
  );
}
