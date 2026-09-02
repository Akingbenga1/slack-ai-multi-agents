import { PageHeader } from "@/components/dashboard/PageHeader";
import { PlatformBillingOverviewPanel } from "@/components/billing/PlatformBillingOverviewPanel";

export default function AdminBillingPage() {
  return (
    <>
      <PageHeader
        title="Billing"
        description="Cross-tenant billing overview — plans, invoices, and payment activity."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Billing" },
        ]}
        className="mb-8"
      />
      <PlatformBillingOverviewPanel />
    </>
  );
}
