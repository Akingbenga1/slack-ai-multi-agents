import Link from "next/link";
import panel from "@/components/dashboard/panel.module.css";
import {
  formatDate,
  formatMoney,
  type MockTenantBilling,
} from "@/lib/mock/billing-data";

type Props = {
  billing: MockTenantBilling;
  invoicesHref: string;
  transactionsHref: string;
};

function planBadge(planStatus: string, planSource: string): string {
  if (planStatus === "active" && planSource === "admin") return panel.badgeOk;
  if (planStatus === "active") return panel.badgeOk;
  return panel.badgeWarn;
}

export function TenantBillingSummaryPanel({
  billing,
  invoicesHref,
  transactionsHref,
}: Props) {
  const planLabel =
    billing.planStatus === "active" && billing.planSource === "admin"
      ? "active · waived"
      : billing.planStatus === "active"
        ? "active · paid"
        : billing.planStatus;

  return (
    <>
      <div className={panel.metrics}>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>Plan</p>
          <p className={panel.metricValue}>{planLabel}</p>
          <p className={panel.metricSub}>{billing.planSource}-managed</p>
        </div>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>MRR</p>
          <p className={panel.metricValue}>
            {billing.mrrCents > 0
              ? formatMoney(billing.mrrCents, billing.currency)
              : "—"}
          </p>
          <p className={panel.metricSub}>monthly recurring</p>
        </div>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>Next invoice</p>
          <p className={panel.metricValue}>{formatDate(billing.nextInvoiceAt)}</p>
        </div>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>Payment method</p>
          <p className={panel.metricValue}>{billing.paymentMethodSummary || "—"}</p>
        </div>
      </div>

      <div className={panel.grid}>
        <section className={panel.section}>
          <div className={panel.sectionHeader}>
            <h2 className={panel.sectionTitle}>Provider details</h2>
          </div>
          <ul className={panel.detailList}>
            <li className={panel.detailItem}>
              <p className={panel.detailLabel}>Provider</p>
              <p className={panel.detailValue}>{billing.provider}</p>
            </li>
            <li className={panel.detailItem}>
              <p className={panel.detailLabel}>Plan status</p>
              <p className={panel.detailValue}>
                <span className={`${panel.badge} ${planBadge(billing.planStatus, billing.planSource)}`}>
                  {planLabel}
                </span>
              </p>
            </li>
            <li className={panel.detailItem}>
              <p className={panel.detailLabel}>Customer ID</p>
              <p className={panel.detailValue}>
                {billing.externalCustomerId ? (
                  <code>{billing.externalCustomerId}</code>
                ) : (
                  "—"
                )}
              </p>
            </li>
            <li className={panel.detailItem}>
              <p className={panel.detailLabel}>Subscription ID</p>
              <p className={panel.detailValue}>
                {billing.externalSubscriptionId ? (
                  <code>{billing.externalSubscriptionId}</code>
                ) : (
                  "—"
                )}
              </p>
            </li>
          </ul>
        </section>

        <section className={panel.section}>
          <div className={panel.sectionHeader}>
            <h2 className={panel.sectionTitle}>Records</h2>
          </div>
          <p className={panel.sectionDesc}>
            Open invoice and transaction lists for this tenant.
          </p>
          <div className={panel.formRow}>
            <Link href={invoicesHref}>
              <button type="button">View invoices</button>
            </Link>
            <Link href={transactionsHref}>
              <button type="button">View transactions</button>
            </Link>
          </div>
        </section>
      </div>
    </>
  );
}
