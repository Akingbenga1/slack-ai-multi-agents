import { getServerSession } from "next-auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { ToolsManagerPanel } from "@/components/tools/ToolsManagerPanel";
import { authOptions } from "@/lib/auth";
import { getMockTenantBilling } from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantToolsPage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const { tenantId } = await params;
  const tenantName = getMockTenantBilling(tenantId).tenantName;

  return (
    <>
      <PageHeader
        title="Agent tools"
        description={`Install and select MCP servers for ${tenantName}.`}
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: tenantName, href: `/admin/tenants/${tenantId}` },
          { label: "Tools" },
        ]}
        className="mb-8"
      />
      <ToolsManagerPanel
        tenantLabel={tenantName}
        createHref={`/admin/tenants/${tenantId}/tools/new`}
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
    </>
  );
}
