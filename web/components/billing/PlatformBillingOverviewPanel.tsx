import Link from "next/link";
import { FileText, Receipt, TrendingUp, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  formatDateTime,
  formatMoney,
  getMockPlatformBillingOverview,
  type MockPlatformBillingRow,
} from "@/lib/mock/billing-data";

const AVATAR_COLORS = [
  "bg-[#ecfdf5] text-[#006c49]",
  "bg-[#e0e7ff] text-[#4648d3]",
  "bg-[#fef9c3] text-[#854d0e]",
  "bg-[#fee2e2] text-[#991b1b]",
  "bg-[#f1f5f9] text-[#475569]",
];

function avatarColor(name: string): string {
  const code = name.trim().charCodeAt(0) || 0;
  return AVATAR_COLORS[code % AVATAR_COLORS.length];
}

function planLabel(row: MockPlatformBillingRow): string {
  if (row.planStatus === "active" && row.planSource === "admin") {
    return "active · waived";
  }
  if (row.planStatus === "active") {
    return "active · paid";
  }
  return row.planStatus;
}

function planBadgeVariant(
  row: MockPlatformBillingRow,
): "success" | "warning" | "muted" {
  if (row.planStatus === "active") return "success";
  if (row.planStatus === "inactive") return "warning";
  return "muted";
}

function TenantAvatar({ name }: { name: string }) {
  const initial = (name.trim()[0] ?? "?").toUpperCase();
  return (
    <span
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-semibold",
        avatarColor(name),
      )}
      aria-hidden
    >
      {initial}
    </span>
  );
}

function SummaryStatCard({
  label,
  icon: Icon,
  footer,
  children,
}: {
  label: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
  footer?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card className="h-full">
      <CardContent className="flex h-full flex-col pt-6">
        <div className="flex items-start justify-between gap-3">
          <p className="text-label-md text-muted-foreground">{label}</p>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
            <Icon size={18} />
          </div>
        </div>
        <div className="mt-3 flex-1">{children}</div>
        {footer ? (
          <p className="mt-3 text-sm text-muted-foreground">{footer}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ProgressBar({
  used,
  limit,
  barClassName,
}: {
  used: number;
  limit: number;
  barClassName?: string;
}) {
  const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
  return (
    <div className="mt-4 h-2 overflow-hidden rounded-full bg-[#f2f4f6]">
      <div
        className={cn("h-full rounded-full transition-all", barClassName ?? "bg-primary")}
        style={{ width: `${pct}%` }}
        role="progressbar"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={limit || 100}
      />
    </div>
  );
}

export function PlatformBillingOverviewPanel() {
  const rows = getMockPlatformBillingOverview();
  const totalMrr = rows.reduce((sum, row) => sum + row.mrrCents, 0);
  const activeCount = rows.filter((row) => row.planStatus === "active").length;
  const openInvoices = rows.reduce((sum, row) => sum + row.openInvoiceCount, 0);
  const paidTenants = rows.filter((row) => row.mrrCents > 0).length;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryStatCard
          label="Platform MRR"
          icon={TrendingUp}
          footer="Monthly recurring revenue across tenants"
        >
          <p className="text-3xl font-bold tracking-tight text-foreground">
            {formatMoney(totalMrr, "usd")}
          </p>
          <ProgressBar
            used={paidTenants}
            limit={rows.length}
            barClassName="bg-primary"
          />
        </SummaryStatCard>

        <SummaryStatCard
          label="Active plans"
          icon={Receipt}
          footer={`${rows.length - activeCount} inactive or waived`}
        >
          <p className="flex items-baseline gap-1">
            <span className="text-3xl font-bold tracking-tight text-foreground">
              {activeCount}
            </span>
            <span className="text-lg font-medium text-muted-foreground">
              / {rows.length}
            </span>
          </p>
          <ProgressBar used={activeCount} limit={rows.length} />
        </SummaryStatCard>

        <SummaryStatCard
          label="Open invoices"
          icon={FileText}
          footer="Unpaid billing documents across tenants"
        >
          <p className="text-3xl font-bold tracking-tight text-foreground">
            {openInvoices}
          </p>
          <ProgressBar
            used={openInvoices}
            limit={Math.max(openInvoices, rows.length)}
            barClassName={openInvoices > 0 ? "bg-[#854d0e]" : "bg-muted"}
          />
        </SummaryStatCard>

        <SummaryStatCard
          label="Tenants"
          icon={Users}
          footer="Organisations with billing records"
        >
          <p className="text-3xl font-bold tracking-tight text-foreground">
            {rows.length}
          </p>
          <ProgressBar used={rows.length} limit={rows.length} />
        </SummaryStatCard>
      </div>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-5">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-headline-md text-foreground">Billing by tenant</h2>
              <Badge variant="muted">{rows.length}</Badge>
            </div>
            <p className="mt-1 text-body-md text-muted-foreground">
              Click a tenant to open billing overview, invoices, and transaction history.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-[#f8fafc]">
                <th
                  scope="col"
                  className="px-6 py-3 text-label-md text-muted-foreground"
                >
                  Tenant
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  Plan
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  MRR
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  Last payment
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  Open invoices
                </th>
                <th
                  scope="col"
                  className="px-6 py-3 text-right text-label-md text-muted-foreground"
                >
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.tenantId}
                  className="border-b border-border last:border-b-0 hover:bg-muted/40"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <TenantAvatar name={row.tenantName} />
                      <div className="min-w-0">
                        <Link
                          href={`/admin/tenants/${row.tenantId}/billing`}
                          className="font-medium text-foreground hover:text-primary"
                        >
                          {row.tenantName}
                        </Link>
                        <p className="truncate text-sm text-muted-foreground">
                          {row.tenantSlug}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <Badge variant={planBadgeVariant(row)}>{planLabel(row)}</Badge>
                  </td>
                  <td className="px-4 py-4 font-medium text-foreground">
                    {row.mrrCents > 0
                      ? formatMoney(row.mrrCents, row.currency)
                      : "—"}
                  </td>
                  <td className="px-4 py-4 text-foreground">
                    {formatDateTime(row.lastPaymentAt)}
                  </td>
                  <td className="px-4 py-4">
                    {row.openInvoiceCount > 0 ? (
                      <Badge variant="warning">{row.openInvoiceCount}</Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap justify-end gap-2">
                      <Link
                        href={`/admin/tenants/${row.tenantId}/billing`}
                        className={buttonVariants({ variant: "outline", size: "sm" })}
                      >
                        Billing
                      </Link>
                      <Link
                        href={`/admin/tenants/${row.tenantId}/billing/invoices`}
                        className={buttonVariants({ variant: "ghost", size: "sm" })}
                      >
                        Invoices
                      </Link>
                      <Link
                        href={`/admin/tenants/${row.tenantId}/billing/transactions`}
                        className={buttonVariants({ variant: "ghost", size: "sm" })}
                      >
                        Transactions
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
