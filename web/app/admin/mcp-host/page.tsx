import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { AdminMcpHostPanel } from "@/components/admin/AdminMcpHostPanel";
import { buttonVariants } from "@/components/ui/button";

export default async function AdminMcpHostPage() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <PageHeader
        title="MCP host"
        description="Check whether registered MCP servers are reachable and ready before the agent uses them."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tools", href: "/admin/tools" },
          { label: "MCP host" },
        ]}
        actions={
          <Link
            href="/admin/tools"
            className={buttonVariants({ variant: "secondary" })}
          >
            All tools
          </Link>
        }
        className="mb-8"
      />
      <AdminMcpHostPanel accessToken={session?.accessToken ?? null} />
    </>
  );
}
