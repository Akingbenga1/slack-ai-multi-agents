import { PageHeader } from "@/components/dashboard/PageHeader";
import { ToolsManagerPanel } from "@/components/tools/ToolsManagerPanel";
import { getMockTenantBilling } from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantToolsPage({ params }: Props) {
  const { tenantId } = await params;
  const tenantName = getMockTenantBilling(tenantId).tenantName;

  return (
    <>
      <PageHeader
        title="Agent tools"
        description={`Register CLI tools and MCP servers for ${tenantName}.`}
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: tenantName, href: `/admin/tenants/${tenantId}` },
          { label: "Tools" },
        ]}
      />
      <ToolsManagerPanel
        tenantLabel={tenantName}
        createHref={`/admin/tenants/${tenantId}/tools/new`}
      />
    </>
  );
}
