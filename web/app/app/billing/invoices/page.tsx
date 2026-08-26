import { PageHeader } from "@/components/dashboard/PageHeader";
import { BillingTabNav } from "@/components/billing/BillingTabNav";
import { orgBillingTabs } from "@/lib/billing-tabs";
import { InvoicesPanel } from "@/components/billing/InvoicesPanel";
import { getMockInvoices, getMockTenantBilling } from "@/lib/mock/billing-data";

const DEMO_TENANT_ID = "11111111-1111-1111-1111-111111111111";

export default function OrgInvoicesPage() {
  const billing = getMockTenantBilling(DEMO_TENANT_ID);
  const invoices = getMockInvoices(DEMO_TENANT_ID);

  return (
    <>
      <PageHeader
        title="Invoices"
        description="Past and current invoices for your organisation."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Billing", href: "/app/billing" },
          { label: "Invoices" },
        ]}
      />
      <BillingTabNav tabs={orgBillingTabs()} />
      <InvoicesPanel invoices={invoices} tenantName={billing.tenantName} />
    </>
  );
}
