import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import panel from "@/components/dashboard/panel.module.css";
import { AdminMcpHostPanel } from "@/components/admin/AdminMcpHostPanel";

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
          <Link href="/admin/tools" className={panel.btnPrimary}>
            All tools
          </Link>
        }
      />
      <AdminMcpHostPanel accessToken={session?.accessToken ?? null} />
    </>
  );
}
