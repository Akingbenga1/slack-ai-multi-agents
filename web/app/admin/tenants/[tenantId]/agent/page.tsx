import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { AgentSettingsPanel } from "@/components/AgentSettingsPanel";
import { getMockTenantBilling } from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantAgentPage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const { tenantId } = await params;
  const tenantName = getMockTenantBilling(tenantId).tenantName;

  return (
    <>
      <PageHeader
        title="Agent settings"
        description={`Agent name, instructions, schedules, and channel allowlist for ${tenantName}.`}
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: tenantName, href: `/admin/tenants/${tenantId}` },
          { label: "Agent" },
        ]}
        className="mb-8"
      />
      <AgentSettingsPanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
    </>
  );
}
