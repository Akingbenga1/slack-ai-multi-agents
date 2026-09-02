import Link from "next/link";
import { getServerSession } from "next-auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { CreateToolForm } from "@/components/tools/CreateToolForm";
import { authOptions } from "@/lib/auth";
import { getMockTenantOptions } from "@/lib/mock/tools-data";

export default async function AdminCreateToolPage() {
  const session = await getServerSession(authOptions);
  const tenants = getMockTenantOptions();

  return (
    <>
      <PageHeader
        title="New tool"
        description="Register a CLI, MCP, or HTTP capability for an organisation — discover from online services or configure manually."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tools", href: "/admin/tools" },
          { label: "New" },
        ]}
        actions={
          <div>
            <Link href="/admin/cli-host">
              CLI host
            </Link>
            <Link href="/admin/mcp-host">
              MCP host
            </Link>
          </div>
        }
        className="mb-8"
      />
      <CreateToolForm
        cancelHref="/admin/tools"
        tenants={tenants}
        accessToken={session?.accessToken ?? null} />
    </>
  );
}
