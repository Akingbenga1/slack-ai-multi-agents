import Link from "next/link";
import { CreditCard, Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  formatDate,
  formatMoney,
  type MockInvoice,
  type MockTenantBilling,
} from "@/lib/mock/billing-data";
import { invoiceStatusVariant } from "@/components/billing/billing-display";

type Props = {
  billing: MockTenantBilling;
  invoices: MockInvoice[];
  invoicesHref: string;
  transactionsHref: string;
};

function planLabel(billing: MockTenantBilling): string {
  if (billing.planStatus === "active" && billing.planSource === "admin") {
    return "active · waived";
  }
  if (billing.planStatus === "active") {
    return "active · paid";
  }
  return billing.planStatus;
}

function planBadgeVariant(
  billing: MockTenantBilling,
): "success" | "warning" | "muted" {
  if (billing.planStatus === "active") return "success";
  if (billing.planStatus === "inactive") return "warning";
  return "muted";
}


function DetailRow({
  label,
  children,
  mono,
}: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 border-b border-border py-3 last:border-b-0 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <div
        className={cn(
          "text-sm font-medium text-foreground sm:text-right",
          mono && "font-mono text-[13px]",
        )}
      >
        {children}
      </div>
    </div>
  );
}

export function TenantBillingSummaryPanel({
  billing,
  invoices,
  invoicesHref,
  transactionsHref,
}: Props) {
  const label = planLabel(billing);
  const recentInvoices = invoices.slice(0, 3);
  const mrrDisplay =
    billing.mrrCents > 0
      ? formatMoney(billing.mrrCents, billing.currency)
      : "—";

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardContent className="flex h-full flex-col pt-6">
          <p className="text-label-md text-muted-foreground">Current plan</p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <p className="text-headline-md text-foreground">{label}</p>
            <Badge variant={planBadgeVariant(billing)}>
              {billing.planStatus === "active" ? "Active" : billing.planStatus}
            </Badge>
          </div>
          <p className="mt-4 text-[2.5rem] font-bold leading-none tracking-tight text-foreground">
            {mrrDisplay}
            {billing.mrrCents > 0 ? (
              <span className="ml-1 text-lg font-semibold text-muted-foreground">
                /mo
              </span>
            ) : null}
          </p>
          <p className="mt-3 text-body-md text-muted-foreground">
            Next invoice: {formatDate(billing.nextInvoiceAt)}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {billing.planSource}-managed
          </p>
          <div className="mt-auto flex flex-wrap gap-3 pt-8">
            <Link href={invoicesHref} className={buttonVariants()}>
              View invoices
            </Link>
            <Link
              href={transactionsHref}
              className={buttonVariants({ variant: "outline" })}
            >
              View transactions
            </Link>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b-0 pb-0">
          <CardTitle>Provider details</CardTitle>
          <CardDescription>
            Payment provider identifiers and subscription linkage for this
            organisation.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-2">
          <DetailRow label="Provider">{billing.provider}</DetailRow>
          <DetailRow label="Plan status">
            <Badge variant={planBadgeVariant(billing)}>{label}</Badge>
          </DetailRow>
          <DetailRow label="Customer ID" mono>
            {billing.externalCustomerId ?? "—"}
          </DetailRow>
          <DetailRow label="Subscription ID" mono>
            {billing.externalSubscriptionId ?? "—"}
          </DetailRow>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b-0 pb-0">
          <CardTitle>Payment method</CardTitle>
          <CardDescription>
            Default payment method on file with the billing provider.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {billing.paymentMethodSummary ? (
            <div className="flex items-center gap-4 rounded-lg border-2 border-primary px-4 py-4">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                <CreditCard className="size-5 text-muted-foreground" aria-hidden />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-foreground">
                    {billing.paymentMethodSummary}
                  </p>
                  <Badge variant="success">Default</Badge>
                </div>
              </div>
            </div>
          ) : (
            <p className="rounded-lg border border-dashed border-border bg-muted/40 px-4 py-8 text-center text-body-md text-muted-foreground">
              No payment method on file — tenant is not linked to a payment
              provider or billing is waived.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b-0 pb-0">
          <div className="flex w-full items-start justify-between gap-4">
            <div>
              <CardTitle>Recent invoices</CardTitle>
              <CardDescription>
                Latest billing documents for this organisation.
              </CardDescription>
            </div>
            {invoices.length > 0 ? (
              <Link
                href={invoicesHref}
                className="shrink-0 text-sm font-medium text-primary hover:underline"
              >
                View all
              </Link>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="px-0 pb-0 pt-2 sm:px-6 sm:pb-6">
          {recentInvoices.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[320px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th
                      scope="col"
                      className="px-6 py-3 text-label-md text-muted-foreground"
                    >
                      Date
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-label-md text-muted-foreground"
                    >
                      Amount
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-label-md text-muted-foreground"
                    >
                      Status
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-3 text-right text-label-md text-muted-foreground"
                    >
                      Invoice
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {recentInvoices.map((inv) => (
                    <tr
                      key={inv.id}
                      className="border-b border-border last:border-b-0 hover:bg-muted/40"
                    >
                      <td className="px-6 py-4 text-foreground">
                        {formatDate(inv.issuedAt)}
                      </td>
                      <td className="px-4 py-4 font-medium text-foreground">
                        {formatMoney(inv.amountCents, inv.currency)}
                      </td>
                      <td className="px-4 py-4">
                        <Badge variant={invoiceStatusVariant(inv.status)}>
                          {inv.status}
                        </Badge>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="inline-flex items-center gap-2 font-mono text-[13px] text-muted-foreground">
                          {inv.number}
                          <Download
                            className="size-4 shrink-0 text-muted-foreground"
                            aria-hidden
                          />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="px-6 pb-6 text-body-md text-muted-foreground">
              No invoices — tenant is not linked to a payment provider.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
