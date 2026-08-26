import Link from "next/link";
import panel from "@/components/dashboard/panel.module.css";
import {
  formatDate,
  formatDateTime,
  formatMoney,
  getMockPlatformBillingOverview,
} from "@/lib/mock/billing-data";

export function PlatformBillingOverviewPanel() {
  const rows = getMockPlatformBillingOverview();
  const totalMrr = rows.reduce((sum, r) => sum + r.mrrCents, 0);
  const activeCount = rows.filter((r) => r.planStatus === "active").length;
  const openInvoices = rows.reduce((sum, r) => sum + r.openInvoiceCount, 0);

  return (
    <>
      <div className={panel.metrics}>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>MRR</p>
          <p className={panel.metricValue}>{formatMoney(totalMrr, "usd")}</p>
          <p className={panel.metricSub}>across tenants</p>
        </div>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>Active plans</p>
          <p className={`${panel.metricValue} ${panel.metricGood}`}>{activeCount}</p>
        </div>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>Open invoices</p>
          <p className={`${panel.metricValue} ${openInvoices > 0 ? panel.metricWarn : ""}`}>
            {openInvoices}
          </p>
        </div>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>Tenants</p>
          <p className={panel.metricValue}>{rows.length}</p>
        </div>
      </div>

      <section className={panel.section}>
        <div className={panel.sectionHeader}>
          <h2 className={panel.sectionTitle}>Billing by tenant</h2>
          <span className={panel.sectionCount}>{rows.length}</span>
        </div>
        <p className={panel.sectionDesc}>
          Click a tenant to open billing overview, invoices, and transaction history.
        </p>

        <div className={panel.tableWrap}>
          <table className={panel.table}>
            <thead>
              <tr>
                <th scope="col">Tenant</th>
                <th scope="col">Plan</th>
                <th scope="col">MRR</th>
                <th scope="col">Last payment</th>
                <th scope="col">Open invoices</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.tenantId}>
                  <td>
                    <Link
                      href={`/admin/tenants/${row.tenantId}/billing`}
                      className={panel.tableLink}
                    >
                      {row.tenantName}
                    </Link>
                    <div className={panel.tableMuted}>{row.tenantSlug}</div>
                  </td>
                  <td>
                    <span
                      className={`${panel.badge} ${
                        row.planStatus === "active" ? panel.badgeOk : panel.badgeWarn
                      }`}
                    >
                      {row.planStatus}
                      {row.planSource === "admin" ? " · waived" : ""}
                    </span>
                  </td>
                  <td>
                    {row.mrrCents > 0
                      ? formatMoney(row.mrrCents, row.currency)
                      : "—"}
                  </td>
                  <td className={panel.tableMuted}>
                    {formatDateTime(row.lastPaymentAt)}
                  </td>
                  <td>{row.openInvoiceCount > 0 ? row.openInvoiceCount : "—"}</td>
                  <td>
                    <Link href={`/admin/tenants/${row.tenantId}/billing/invoices`}>
                      Invoices
                    </Link>
                    {" · "}
                    <Link href={`/admin/tenants/${row.tenantId}/billing/transactions`}>
                      Txns
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
