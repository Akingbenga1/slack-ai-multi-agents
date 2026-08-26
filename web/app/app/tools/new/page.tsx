import { getServerSession } from "next-auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { CreateToolForm } from "@/components/tools/CreateToolForm";
import { authOptions } from "@/lib/auth";
import { sessionTenantId } from "@/lib/tenant";

export default async function OrgCreateToolPage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <>
      <PageHeader
        title="New tool"
        description="Create a CLI tool, MCP tool, or HTTP request tool for your organisation."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Tools", href: "/app/tools" },
          { label: "New" },
        ]}
      />
      <CreateToolForm
        cancelHref="/app/tools"
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
    </>
  );
}
