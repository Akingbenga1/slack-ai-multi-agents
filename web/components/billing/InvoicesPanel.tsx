import { Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  formatDate,
  formatMoney,
  type MockInvoice,
} from "@/lib/mock/billing-data";
import { invoiceStatusVariant } from "@/components/billing/billing-display";

type Props = {
  invoices: MockInvoice[];
  tenantName?: string;
};

export function InvoicesPanel({ invoices, tenantName }: Props) {
  const description = tenantName
    ? `Billing documents issued to ${tenantName}.`
    : "Billing documents for this organisation.";

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-5">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-headline-md text-foreground">Invoices</h2>
            <Badge variant="muted">{invoices.length}</Badge>
          </div>
          <p className="mt-1 text-body-md text-muted-foreground">{description}</p>
        </div>
      </div>

      {invoices.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-[#f8fafc]">
                <th
                  scope="col"
                  className="px-6 py-3 text-label-md text-muted-foreground"
                >
                  Invoice
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  Period
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  Issued
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  Due
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
                  <span className="sr-only">Download</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr
                  key={inv.id}
                  className="border-b border-border last:border-b-0 hover:bg-muted/40"
                >
                  <td className="px-6 py-4">
                    <p className="font-medium text-foreground">{inv.number}</p>
                    <p className="mt-1 font-mono text-[13px] text-muted-foreground">
                      {inv.id}
                    </p>
                  </td>
                  <td className="px-4 py-4 text-foreground">
                    {formatDate(inv.periodStart)} – {formatDate(inv.periodEnd)}
                  </td>
                  <td className="px-4 py-4 text-foreground">
                    {formatDate(inv.issuedAt)}
                  </td>
                  <td className="px-4 py-4 text-foreground">
                    {formatDate(inv.dueAt)}
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
                    <span
                      className="inline-flex size-8 items-center justify-center rounded-lg text-muted-foreground"
                      aria-hidden
                    >
                      <Download className="size-4" />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <CardContent>
          <p className="rounded-lg border border-dashed border-border bg-muted/40 px-4 py-10 text-center text-body-md text-muted-foreground">
            No invoices — tenant is not linked to a payment provider.
          </p>
        </CardContent>
      )}
    </Card>
  );
}
