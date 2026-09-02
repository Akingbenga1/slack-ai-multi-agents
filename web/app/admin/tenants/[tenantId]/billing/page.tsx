import { AdminTenantBillingFrame } from "@/components/billing/AdminTenantBillingFrame";
import { TenantBillingSummaryPanel } from "@/components/billing/TenantBillingSummaryPanel";
import {
  getMockInvoices,
  getMockTenantBilling,
} from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantBillingPage({ params }: Props) {
  const { tenantId } = await params;
  const billing = getMockTenantBilling(tenantId);
  const invoices = getMockInvoices(tenantId);
  const base = `/admin/tenants/${tenantId}/billing`;

  return (
    <AdminTenantBillingFrame
      tenantId={tenantId}
      title="Tenant billing"
      description={`Billing overview for ${billing.tenantName} — plan, provider IDs, and links to records.`}
      breadcrumbs={[
        { label: "Overview", href: "/admin" },
        { label: "Tenants", href: "/admin/tenants" },
        { label: billing.tenantName, href: `/admin/tenants/${tenantId}` },
        { label: "Billing" },
      ]}
    >
      <TenantBillingSummaryPanel
        billing={billing}
        invoices={invoices}
        invoicesHref={`${base}/invoices`}
        transactionsHref={`${base}/transactions`}
      />
    </AdminTenantBillingFrame>
  );
}
