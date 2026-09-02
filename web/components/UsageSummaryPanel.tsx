"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  Filter,
  RefreshCw,
  Zap,
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

type EventAgg = {
  event_type: string;
  event_count: number;
  units: number;
};

type BudgetSlice = {
  key: string;
  limit: number;
  used: number;
  remaining: number;
  window: string;
};

type UsageSummary = {
  tenant_id: string;
  window: string;
  since: string;
  as_of: string;
  by_event_type: EventAgg[];
  totals: { event_count: number; units: number };
  plan_active: boolean;
  budgets: BudgetSlice[];
};

type UsageEventRow = {
  id: string;
  event_type: string;
  units: number;
  meta: Record<string, unknown>;
  created_at: string | null;
};

type JobLogRow = {
  id: string;
  kind: string;
  status: string;
  error: string | null;
  created_at: string | null;
  finished_at: string | null;
};

const EVENT_FILTER_OPTIONS = [
  { value: "", label: "All events" },
  { value: "slack_mention", label: "Mentions" },
  { value: "llm_tokens", label: "Token usage" },
  { value: "job", label: "Jobs" },
  { value: "sync_run", label: "Sync runs" },
  { value: "ingest", label: "Ingest" },
  { value: "report_post", label: "Report posts" },
] as const;

const TABLE_PAGE_SIZE = 10;

const selectClassName =
  "rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

async function fetchSummary(
  accessToken: string,
  tenantId: string | null,
  window: "day" | "month",
): Promise<UsageSummary> {
  const data = await apiClient.get<UsageSummary>(
    `/usage/summary?window=${window}`,
    { accessToken, clientId: tenantId },
  );
  if (!data) {
    throw new Error("Empty usage summary");
  }
  return data;
}

async function fetchEvents(
  accessToken: string,
  tenantId: string | null,
  eventType: string,
  page: number,
): Promise<{ events: UsageEventRow[]; total: number }> {
  const offset = (page - 1) * TABLE_PAGE_SIZE;
  const params = new URLSearchParams({
    limit: String(TABLE_PAGE_SIZE),
    offset: String(offset),
  });
  if (eventType) {
    params.set("event_type", eventType);
  }
  const body = await apiClient.get<{
    events: UsageEventRow[];
    total: number;
  }>(`/usage/events?${params.toString()}`, {
    accessToken,
    clientId: tenantId,
  });
  const events = body?.events || [];
  return {
    events,
    // Older API builds omit `total`; fall back so rows still render and page 1 paginates.
    total: body?.total ?? events.length,
  };
}

async function fetchJobs(
  accessToken: string,
  tenantId: string | null,
  failedOnly: boolean,
  page: number,
): Promise<{ jobs: JobLogRow[]; total: number }> {
  const offset = (page - 1) * TABLE_PAGE_SIZE;
  const params = new URLSearchParams({
    limit: String(TABLE_PAGE_SIZE),
    offset: String(offset),
  });
  if (failedOnly) {
    params.set("status", "failed");
  }
  const body = await apiClient.get<{ jobs: JobLogRow[]; total: number }>(
    `/usage/jobs?${params.toString()}`,
    { accessToken, clientId: tenantId },
  );
  const jobs = body?.jobs || [];
  return {
    jobs,
    total: body?.total ?? jobs.length,
  };
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

function formatBudgetKey(key: string): string {
  return key.replace(/_/g, " ");
}

function budgetProgressClass(used: number, limit: number): string {
  if (limit <= 0) return "bg-muted";
  const pct = used / limit;
  if (pct >= 1) return "bg-danger";
  if (pct >= 0.85) return "bg-warning";
  return "bg-primary";
}

function BudgetRow({ budget }: { budget: BudgetSlice }) {
  const pct =
    budget.limit > 0
      ? Math.min(100, (budget.used / budget.limit) * 100)
      : 0;

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium capitalize text-foreground">
          {formatBudgetKey(budget.key)}
        </p>
        <Badge variant="muted" className="capitalize">
          {budget.window}
        </Badge>
      </div>
      <p className="mt-2 text-headline-md text-foreground">
        {budget.used.toLocaleString()}
        {budget.limit > 0 ? (
          <span className="text-body-md text-muted-foreground">
            {" "}
            / {budget.limit.toLocaleString()}
          </span>
        ) : null}
      </p>
      {budget.limit > 0 ? (
        <>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                budgetProgressClass(budget.used, budget.limit),
              )}
              style={{ width: `${pct}%` }}
              role="progressbar"
              aria-valuenow={budget.used}
              aria-valuemin={0}
              aria-valuemax={budget.limit}
            />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {budget.remaining.toLocaleString()} remaining
          </p>
        </>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">No limit configured</p>
      )}
    </div>
  );
}

function LoadingBlock({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }, (_, key) => (
        <div key={key} className="h-10 animate-pulse rounded-lg bg-muted" />
      ))}
    </div>
  );
}

function totalPages(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

type TablePaginationProps = {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
};

function TablePagination({
  page,
  pageSize,
  total,
  onPageChange,
}: TablePaginationProps) {
  if (total === 0) {
    return null;
  }

  const pages = totalPages(total, pageSize);
  const safePage = Math.min(Math.max(1, page), pages);
  const start = (safePage - 1) * pageSize + 1;
  const end = Math.min(safePage * pageSize, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-6 py-4">
      <p className="text-sm text-muted-foreground">
        Showing {start.toLocaleString()}–{end.toLocaleString()} of{" "}
        {total.toLocaleString()}
      </p>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="rounded-full"
          disabled={safePage <= 1}
          onClick={() => onPageChange(safePage - 1)}
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>
        <span className="min-w-[5.5rem] text-center text-sm text-muted-foreground">
          Page {safePage} of {pages}
        </span>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="rounded-full"
          disabled={safePage >= pages}
          onClick={() => onPageChange(safePage + 1)}
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

export function UsageSummaryPanel({ accessToken, tenantId }: Props) {
  const [window, setWindow] = useState<"day" | "month">("day");
  const [eventFilter, setEventFilter] = useState<string>("");
  const [failedOnly, setFailedOnly] = useState(false);
  const [data, setData] = useState<UsageSummary | null | undefined>(undefined);
  const [events, setEvents] = useState<UsageEventRow[] | null>(null);
  const [eventsTotal, setEventsTotal] = useState(0);
  const [eventsPage, setEventsPage] = useState(1);
  const [jobs, setJobs] = useState<JobLogRow[] | null>(null);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsPage, setJobsPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadSummary = useCallback(async () => {
    if (!accessToken) {
      setData(null);
      return;
    }
    const summary = await fetchSummary(accessToken, tenantId, window);
    setData(summary);
  }, [accessToken, tenantId, window]);

  const loadEvents = useCallback(async () => {
    if (!accessToken) {
      setEvents(null);
      setEventsTotal(0);
      return;
    }
    const ev = await fetchEvents(accessToken, tenantId, eventFilter, eventsPage);
    setEvents(ev.events);
    setEventsTotal(ev.total);
  }, [accessToken, tenantId, eventFilter, eventsPage]);

  const loadJobs = useCallback(async () => {
    if (!accessToken) {
      setJobs(null);
      setJobsTotal(0);
      return;
    }
    const jb = await fetchJobs(accessToken, tenantId, failedOnly, jobsPage);
    setJobs(jb.jobs);
    setJobsTotal(jb.total);
  }, [accessToken, tenantId, failedOnly, jobsPage]);

  const loadAll = useCallback(async () => {
    if (!accessToken) {
      setData(null);
      setEvents(null);
      setEventsTotal(0);
      setJobs(null);
      setJobsTotal(0);
      return;
    }
    const [summary, ev, jb] = await Promise.all([
      fetchSummary(accessToken, tenantId, window),
      fetchEvents(accessToken, tenantId, eventFilter, eventsPage),
      fetchJobs(accessToken, tenantId, failedOnly, jobsPage),
    ]);
    setData(summary);
    setEvents(ev.events);
    setEventsTotal(ev.total);
    setJobs(jb.jobs);
    setJobsTotal(jb.total);
  }, [
    accessToken,
    tenantId,
    window,
    eventFilter,
    failedOnly,
    eventsPage,
    jobsPage,
  ]);

  useEffect(() => {
    let cancelled = false;
    setData(undefined);
    setError(null);
    loadSummary().catch((err) => {
      if (!cancelled) {
        setData(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loadSummary]);

  useEffect(() => {
    let cancelled = false;
    setEvents(null);
    loadEvents().catch((err) => {
      if (!cancelled) {
        setEvents(null);
        setEventsTotal(0);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loadEvents]);

  useEffect(() => {
    let cancelled = false;
    setJobs(null);
    loadJobs().catch((err) => {
      if (!cancelled) {
        setJobs(null);
        setJobsTotal(0);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loadJobs]);

  async function onRefresh() {
    setRefreshing(true);
    setError(null);
    try {
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-headline-md">Filters</CardTitle>
              </div>
              <CardDescription className="mt-1">
                Adjust the reporting window and drill into events or failed jobs.
              </CardDescription>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => onRefresh()}
              disabled={!accessToken || refreshing}
            >
              <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4 pt-6">
          <label className="grid gap-2 text-sm">
            <span className="font-medium text-foreground">Window</span>
            <select
              id="usage-window"
              value={window}
              onChange={(e) => {
                setWindow(e.target.value as "day" | "month");
              }}
              className={selectClassName}
            >
              <option value="day">UTC day</option>
              <option value="month">UTC month</option>
            </select>
          </label>
          <label className="grid gap-2 text-sm">
            <span className="font-medium text-foreground">Event type</span>
            <select
              id="event-filter"
              value={eventFilter}
              onChange={(e) => {
                setEventFilter(e.target.value);
                setEventsPage(1);
              }}
              className={selectClassName}
            >
              {EVENT_FILTER_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-end gap-2 pb-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={failedOnly}
              onChange={(e) => {
                setFailedOnly(e.target.checked);
                setJobsPage(1);
              }}
              className="h-4 w-4 rounded border-border"
            />
            Failed jobs only
          </label>
        </CardContent>
      </Card>

      {error ? (
        <p className="text-body-md text-danger" role="alert">
          {error}
        </p>
      ) : null}

      {data === undefined ? (
        <LoadingBlock rows={4} />
      ) : data === null ? (
        <Card>
          <CardContent className="py-10 text-center text-body-md text-muted-foreground">
            No usage data. Sign in with an API token and ensure the gateway is up.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-label-md text-muted-foreground">Plan</p>
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                    <Zap className="h-4 w-4" />
                  </div>
                </div>
                <div className="mt-3">
                  <Badge variant={data.plan_active ? "success" : "warning"}>
                    {data.plan_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-label-md text-muted-foreground">Events</p>
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                    <Activity className="h-4 w-4" />
                  </div>
                </div>
                <p className="mt-3 text-headline-md text-foreground">
                  {data.totals.event_count.toLocaleString()}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-label-md text-muted-foreground">Units</p>
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                    <Briefcase className="h-4 w-4" />
                  </div>
                </div>
                <p className="mt-3 text-headline-md text-foreground">
                  {data.totals.units.toLocaleString()}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Since {formatWhen(data.since)}
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <Card>
                <div className="border-b border-border px-6 py-5">
                  <h2 className="text-headline-md text-foreground">By event type</h2>
                  <p className="mt-1 text-body-md text-muted-foreground">
                    Aggregated counts for the selected {window === "day" ? "day" : "month"}.
                  </p>
                </div>
                <CardContent className="px-0 pb-0 pt-0">
                  {data.by_event_type.length === 0 ? (
                    <p className="px-6 py-8 text-center text-body-md text-muted-foreground">
                      No events in this window.
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[420px] text-left text-sm">
                        <thead>
                          <tr className="border-b border-border bg-[#f8fafc]">
                            <th
                              scope="col"
                              className="px-6 py-3 text-label-md text-muted-foreground"
                            >
                              Type
                            </th>
                            <th
                              scope="col"
                              className="px-4 py-3 text-right text-label-md text-muted-foreground"
                            >
                              Count
                            </th>
                            <th
                              scope="col"
                              className="px-6 py-3 text-right text-label-md text-muted-foreground"
                            >
                              Units
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.by_event_type.map((row) => (
                            <tr
                              key={row.event_type}
                              className="border-b border-border last:border-b-0 hover:bg-muted/40"
                            >
                              <td className="px-6 py-3 text-foreground">
                                {row.event_type}
                              </td>
                              <td className="px-4 py-3 text-right text-muted-foreground">
                                {row.event_count.toLocaleString()}
                              </td>
                              <td className="px-6 py-3 text-right text-muted-foreground">
                                {row.units.toLocaleString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-6 py-5">
                  <div>
                    <h2 className="text-headline-md text-foreground">Recent events</h2>
                    <p className="mt-1 text-body-md text-muted-foreground">
                      Latest usage events matching the filter.
                    </p>
                  </div>
                  {eventsTotal > 0 ? (
                    <Badge variant="muted">{eventsTotal}</Badge>
                  ) : null}
                </div>
                <CardContent className="px-0 pb-0 pt-0">
                  {!events?.length ? (
                    <p className="px-6 py-8 text-center text-body-md text-muted-foreground">
                      No recent usage events.
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[520px] text-left text-sm">
                        <thead>
                          <tr className="border-b border-border bg-[#f8fafc]">
                            <th
                              scope="col"
                              className="px-6 py-3 text-label-md text-muted-foreground"
                            >
                              When
                            </th>
                            <th
                              scope="col"
                              className="px-4 py-3 text-label-md text-muted-foreground"
                            >
                              Type
                            </th>
                            <th
                              scope="col"
                              className="px-6 py-3 text-right text-label-md text-muted-foreground"
                            >
                              Units
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {events.map((event) => (
                            <tr
                              key={event.id}
                              className="border-b border-border last:border-b-0 hover:bg-muted/40"
                            >
                              <td className="px-6 py-3 text-muted-foreground">
                                {formatWhen(event.created_at)}
                              </td>
                              <td className="px-4 py-3 text-foreground">
                                {event.event_type}
                              </td>
                              <td className="px-6 py-3 text-right text-muted-foreground">
                                {event.units.toLocaleString()}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <TablePagination
                    page={eventsPage}
                    pageSize={TABLE_PAGE_SIZE}
                    total={eventsTotal}
                    onPageChange={setEventsPage}
                  />
                </CardContent>
              </Card>

              <Card>
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-6 py-5">
                  <div>
                    <h2 className="text-headline-md text-foreground">
                      Recent jobs{failedOnly ? " (errors)" : ""}
                    </h2>
                    <p className="mt-1 text-body-md text-muted-foreground">
                      Background job log for ingest, sync, and reports.
                    </p>
                  </div>
                  {jobsTotal > 0 ? (
                    <Badge variant={failedOnly ? "danger" : "muted"}>
                      {jobsTotal}
                    </Badge>
                  ) : null}
                </div>
                <CardContent className="px-0 pb-0 pt-0">
                  {!jobs?.length ? (
                    <p className="px-6 py-8 text-center text-body-md text-muted-foreground">
                      {failedOnly ? "No failed jobs." : "No recent jobs."}
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
                              When
                            </th>
                            <th
                              scope="col"
                              className="px-4 py-3 text-label-md text-muted-foreground"
                            >
                              Kind
                            </th>
                            <th
                              scope="col"
                              className="px-4 py-3 text-label-md text-muted-foreground"
                            >
                              Status
                            </th>
                            <th
                              scope="col"
                              className="px-6 py-3 text-label-md text-muted-foreground"
                            >
                              Error
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {jobs.map((job) => (
                            <tr
                              key={job.id}
                              className="border-b border-border last:border-b-0 hover:bg-muted/40"
                            >
                              <td className="px-6 py-3 text-muted-foreground">
                                {formatWhen(job.finished_at || job.created_at)}
                              </td>
                              <td className="px-4 py-3 text-foreground">{job.kind}</td>
                              <td className="px-4 py-3">
                                <Badge
                                  variant={jobStatusVariant(job.status)}
                                  className="capitalize"
                                >
                                  {job.status}
                                </Badge>
                              </td>
                              <td className="px-6 py-3 text-sm text-danger">
                                {job.error ? (
                                  <span className="inline-flex items-start gap-1">
                                    <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                                    {job.error}
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground">—</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <TablePagination
                    page={jobsPage}
                    pageSize={TABLE_PAGE_SIZE}
                    total={jobsTotal}
                    onPageChange={setJobsPage}
                  />
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              <Card>
                <CardHeader className="border-b border-border">
                  <CardTitle className="text-headline-md">Budgets</CardTitle>
                  <CardDescription>
                    Consumption against configured plan limits.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 pt-6">
                  {data.budgets.every((budget) => budget.limit === 0) ? (
                    <p className="text-body-md text-muted-foreground">
                      No budgets while the plan is inactive — subscribe under Billing.
                    </p>
                  ) : (
                    data.budgets.map((budget) => (
                      <BudgetRow key={budget.key} budget={budget} />
                    ))
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="border-b border-border">
                  <CardTitle className="text-headline-md">Window</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 pt-6 text-sm text-muted-foreground">
                  <p>
                    <span className="font-medium text-foreground">Since:</span>{" "}
                    {formatWhen(data.since)}
                  </p>
                  <p>
                    <span className="font-medium text-foreground">As of:</span>{" "}
                    {formatWhen(data.as_of)}
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
