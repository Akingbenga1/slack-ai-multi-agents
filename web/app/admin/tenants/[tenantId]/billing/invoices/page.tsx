import { AdminTenantBillingFrame } from "@/components/billing/AdminTenantBillingFrame";
import { InvoicesPanel } from "@/components/billing/InvoicesPanel";
import { getMockInvoices, getMockTenantBilling } from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantInvoicesPage({ params }: Props) {
  const { tenantId } = await params;
  const billing = getMockTenantBilling(tenantId);
  const invoices = getMockInvoices(tenantId);

  return (
    <AdminTenantBillingFrame
      tenantId={tenantId}
      title="Invoices"
      description={`Invoice history for ${billing.tenantName}.`}
      breadcrumbs={[
        { label: "Overview", href: "/admin" },
        { label: "Tenants", href: "/admin/tenants" },
        { label: billing.tenantName, href: `/admin/tenants/${tenantId}` },
        { label: "Billing", href: `/admin/tenants/${tenantId}/billing` },
        { label: "Invoices" },
      ]}
    >
      <InvoicesPanel invoices={invoices} tenantName={billing.tenantName} />
    </AdminTenantBillingFrame>
  );
}
