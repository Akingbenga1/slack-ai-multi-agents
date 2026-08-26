import { PageHeader } from "@/components/dashboard/PageHeader";
import { TenantBillingSummaryPanel } from "@/components/billing/TenantBillingSummaryPanel";
import { getMockTenantBilling } from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantBillingPage({ params }: Props) {
  const { tenantId } = await params;
  const billing = getMockTenantBilling(tenantId);
  const base = `/admin/tenants/${tenantId}/billing`;

  return (
    <>
      <PageHeader
        title="Tenant billing"
        description={`Billing overview for ${billing.tenantName} — plan, provider IDs, and links to records.`}
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: billing.tenantName, href: `/admin/tenants/${tenantId}` },
          { label: "Billing" },
        ]}
      />
      <TenantBillingSummaryPanel
        billing={billing}
        invoicesHref={`${base}/invoices`}
        transactionsHref={`${base}/transactions`}
      />
    </>
  );
}
