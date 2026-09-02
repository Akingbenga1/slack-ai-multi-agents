import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { UsageSummaryPanel } from "@/components/UsageSummaryPanel";
import { getMockTenantBilling } from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantUsagePage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const { tenantId } = await params;
  const tenantName = getMockTenantBilling(tenantId).tenantName;

  return (
    <>
      <PageHeader
        title="Logs & usage"
        description={`Mentions, jobs, errors, and token usage for ${tenantName}.`}
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: tenantName, href: `/admin/tenants/${tenantId}` },
          { label: "Usage" },
        ]}
        className="mb-8"
      />
      <UsageSummaryPanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
    </>
  );
}
