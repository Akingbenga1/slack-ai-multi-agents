import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  formatDateTime,
  formatMoney,
  type MockTransaction,
} from "@/lib/mock/billing-data";
import {
  transactionStatusVariant,
  transactionTypeLabel,
  transactionTypeVariant,
} from "@/components/billing/billing-display";

type Props = {
  transactions: MockTransaction[];
  tenantName?: string;
};

export function TransactionsPanel({ transactions, tenantName }: Props) {
  const description = tenantName
    ? `Payments, refunds, and adjustments for ${tenantName}.`
    : "Payments, refunds, and adjustments for this organisation.";

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-5">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-headline-md text-foreground">Transaction history</h2>
            <Badge variant="muted">{transactions.length}</Badge>
          </div>
          <p className="mt-1 text-body-md text-muted-foreground">{description}</p>
        </div>
      </div>

      {transactions.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="border-b border-border bg-[#f8fafc]">
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
                  Type
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  Description
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  Method
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-label-md text-muted-foreground"
                >
                  Amount
                </th>
                <th
                  scope="col"
                  className="px-6 py-3 text-label-md text-muted-foreground"
                >
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((txn) => (
                <tr
                  key={txn.id}
                  className="border-b border-border last:border-b-0 hover:bg-muted/40"
                >
                  <td className="px-6 py-4 whitespace-nowrap text-foreground">
                    {formatDateTime(txn.occurredAt)}
                  </td>
                  <td className="px-4 py-4">
                    <Badge variant={transactionTypeVariant(txn.type)}>
                      {transactionTypeLabel(txn.type)}
                    </Badge>
                  </td>
                  <td className="max-w-xs px-4 py-4">
                    <p className="text-foreground">{txn.description}</p>
                    <p className="mt-1 font-mono text-[13px] text-muted-foreground">
                      {txn.id}
                    </p>
                  </td>
                  <td className="px-4 py-4 text-foreground">
                    {txn.paymentMethod}
                  </td>
                  <td className="px-4 py-4 font-medium text-foreground">
                    {txn.amountCents === 0
                      ? "—"
                      : formatMoney(txn.amountCents, txn.currency)}
                  </td>
                  <td className="px-6 py-4">
                    <Badge variant={transactionStatusVariant(txn.status)}>
                      {txn.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <CardContent>
          <p className="rounded-lg border border-dashed border-border bg-muted/40 px-4 py-10 text-center text-body-md text-muted-foreground">
            No transactions — tenant is not linked to a payment provider.
          </p>
        </CardContent>
      )}
    </Card>
  );
}
