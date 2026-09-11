import { getServerSession } from "next-auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { ToolsManagerPanel } from "@/components/tools/ToolsManagerPanel";
import { authOptions } from "@/lib/auth";
import { sessionTenantId } from "@/lib/tenant";

export default async function OrgToolsPage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <>
      <PageHeader
        title="Tools"
        description="Register CLI tools and MCP servers for your organisation's AI agent."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Tools" },
        ]}
        className="mb-8"
      />
      <ToolsManagerPanel
        createHref="/app/tools/new"
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
    </>
  );
}
