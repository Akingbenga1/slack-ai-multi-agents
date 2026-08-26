import panel from "@/components/dashboard/panel.module.css";
import {
  formatDate,
  formatMoney,
  type MockInvoice,
} from "@/lib/mock/billing-data";

type Props = {
  invoices: MockInvoice[];
  tenantName?: string;
};

function statusClass(status: MockInvoice["status"]): string {
  if (status === "paid") return panel.badgeOk;
  if (status === "open") return panel.badgeWarn;
  return panel.badgeNeutral;
}

export function InvoicesPanel({ invoices, tenantName }: Props) {
  return (
    <section className={panel.section}>
      <div className={panel.sectionHeader}>
        <h2 className={panel.sectionTitle}>Invoices</h2>
        <span className={panel.sectionCount}>{invoices.length}</span>
      </div>
      <p className={panel.sectionDesc}>
        {tenantName
          ? `Billing documents issued to ${tenantName}.`
          : "Billing documents for this organisation."}
      </p>

      {invoices.length > 0 ? (
        <div className={panel.tableWrap}>
          <table className={panel.table}>
            <thead>
              <tr>
                <th scope="col">Invoice</th>
                <th scope="col">Period</th>
                <th scope="col">Issued</th>
                <th scope="col">Due</th>
                <th scope="col">Amount</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td>
                    <span className={panel.tableLink}>{inv.number}</span>
                    <div className={panel.tableMuted}>
                      <code>{inv.id}</code>
                    </div>
                  </td>
                  <td className={panel.tableMuted}>
                    {formatDate(inv.periodStart)} – {formatDate(inv.periodEnd)}
                  </td>
                  <td className={panel.tableMuted}>{formatDate(inv.issuedAt)}</td>
                  <td className={panel.tableMuted}>{formatDate(inv.dueAt)}</td>
                  <td>{formatMoney(inv.amountCents, inv.currency)}</td>
                  <td>
                    <span className={`${panel.badge} ${statusClass(inv.status)}`}>
                      {inv.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className={panel.empty}>No invoices — tenant is not linked to a payment provider.</p>
      )}
    </section>
  );
}
