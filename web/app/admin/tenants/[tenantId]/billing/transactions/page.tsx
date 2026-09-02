import { AdminTenantBillingFrame } from "@/components/billing/AdminTenantBillingFrame";
import { TransactionsPanel } from "@/components/billing/TransactionsPanel";
import {
  getMockTenantBilling,
  getMockTransactions,
} from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantTransactionsPage({ params }: Props) {
  const { tenantId } = await params;
  const billing = getMockTenantBilling(tenantId);
  const transactions = getMockTransactions(tenantId);

  return (
    <AdminTenantBillingFrame
      tenantId={tenantId}
      title="Transactions"
      description={`Payment activity for ${billing.tenantName}.`}
      breadcrumbs={[
        { label: "Overview", href: "/admin" },
        { label: "Tenants", href: "/admin/tenants" },
        { label: billing.tenantName, href: `/admin/tenants/${tenantId}` },
        { label: "Billing", href: `/admin/tenants/${tenantId}/billing` },
        { label: "Transactions" },
      ]}
    >
      <TransactionsPanel
        transactions={transactions}
        tenantName={billing.tenantName}
      />
    </AdminTenantBillingFrame>
  );
}
