import { getServerSession } from "next-auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { CreateToolForm } from "@/components/tools/CreateToolForm";
import { authOptions } from "@/lib/auth";
import { getMockTenantBilling } from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantCreateToolPage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const { tenantId } = await params;
  const tenantName = getMockTenantBilling(tenantId).tenantName;

  return (
    <>
      <PageHeader
        title="New tool"
        description={`Create a CLI or HTTP tool for ${tenantName}. Install MCP servers from the tenant Tools page.`}
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: tenantName, href: `/admin/tenants/${tenantId}` },
          { label: "Tools", href: `/admin/tenants/${tenantId}/tools` },
          { label: "New" },
        ]}
        className="mb-8"
      />
      <CreateToolForm
        cancelHref={`/admin/tenants/${tenantId}/tools`}
        tenantLabel={tenantName}
        tenantId={tenantId}
        initialTenantId={tenantId}
        accessToken={session?.accessToken ?? null}
      />
    </>
  );
}
