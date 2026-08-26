import panel from "@/components/dashboard/panel.module.css";
import {
  formatDateTime,
  formatMoney,
  type MockTransaction,
} from "@/lib/mock/billing-data";

type Props = {
  transactions: MockTransaction[];
  tenantName?: string;
};

function statusClass(status: MockTransaction["status"]): string {
  if (status === "succeeded") return panel.badgeOk;
  if (status === "pending") return panel.badgeWarn;
  return panel.badgeError;
}

function typeLabel(type: MockTransaction["type"]): string {
  if (type === "charge") return "Charge";
  if (type === "refund") return "Refund";
  if (type === "adjustment") return "Adjustment";
  return "Payout";
}

export function TransactionsPanel({ transactions, tenantName }: Props) {
  return (
    <section className={panel.section}>
      <div className={panel.sectionHeader}>
        <h2 className={panel.sectionTitle}>Transaction history</h2>
        <span className={panel.sectionCount}>{transactions.length}</span>
      </div>
      <p className={panel.sectionDesc}>
        {tenantName
          ? `Payments, refunds, and adjustments for ${tenantName}.`
          : "Payments, refunds, and adjustments for this organisation."}
      </p>

      {transactions.length > 0 ? (
        <div className={panel.tableWrap}>
          <table className={panel.table}>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Type</th>
                <th scope="col">Description</th>
                <th scope="col">Method</th>
                <th scope="col">Amount</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((txn) => (
                <tr key={txn.id}>
                  <td className={panel.tableMuted}>{formatDateTime(txn.occurredAt)}</td>
                  <td>{typeLabel(txn.type)}</td>
                  <td>
                    {txn.description}
                    <div className={panel.tableMuted}>
                      <code>{txn.id}</code>
                    </div>
                  </td>
                  <td className={panel.tableMuted}>{txn.paymentMethod}</td>
                  <td>
                    {txn.amountCents === 0
                      ? "—"
                      : formatMoney(txn.amountCents, txn.currency)}
                  </td>
                  <td>
                    <span className={`${panel.badge} ${statusClass(txn.status)}`}>
                      {txn.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className={panel.empty}>
          No transactions — tenant is not linked to a payment provider.
        </p>
      )}
    </section>
  );
}
