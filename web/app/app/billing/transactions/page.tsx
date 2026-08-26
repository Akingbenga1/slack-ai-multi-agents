import { PageHeader } from "@/components/dashboard/PageHeader";
import { BillingTabNav } from "@/components/billing/BillingTabNav";
import { orgBillingTabs } from "@/lib/billing-tabs";
import { TransactionsPanel } from "@/components/billing/TransactionsPanel";
import { getMockTenantBilling, getMockTransactions } from "@/lib/mock/billing-data";

const DEMO_TENANT_ID = "11111111-1111-1111-1111-111111111111";

export default function OrgTransactionsPage() {
  const billing = getMockTenantBilling(DEMO_TENANT_ID);
  const transactions = getMockTransactions(DEMO_TENANT_ID);

  return (
    <>
      <PageHeader
        title="Transactions"
        description="Charges, refunds, and adjustments on your account."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Billing", href: "/app/billing" },
          { label: "Transactions" },
        ]}
      />
      <BillingTabNav tabs={orgBillingTabs()} />
      <TransactionsPanel transactions={transactions} tenantName={billing.tenantName} />
    </>
  );
}
