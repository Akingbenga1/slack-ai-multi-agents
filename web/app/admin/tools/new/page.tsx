import Link from "next/link";
import { getServerSession } from "next-auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { CreateToolForm } from "@/components/tools/CreateToolForm";
import { authOptions } from "@/lib/auth";
import { getMockTenantOptions } from "@/lib/mock/tools-data";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default async function AdminCreateToolPage() {
  const session = await getServerSession(authOptions);
  const tenants = getMockTenantOptions();

  return (
    <>
      <PageHeader
        title="New tool"
        description="Register a CLI or HTTP capability for an organisation. Install MCP servers from each tenant's Tools page."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tools", href: "/admin/tools" },
          { label: "New" },
        ]}
        actions={
          <Link
            href="/admin/cli-host"
            className={cn(buttonVariants({ variant: "secondary" }))}
          >
            CLI host
          </Link>
        }
        className="mb-8"
      />
      <CreateToolForm
        cancelHref="/admin/tools"
        tenants={tenants}
        accessToken={session?.accessToken ?? null}
      />
    </>
  );
}
