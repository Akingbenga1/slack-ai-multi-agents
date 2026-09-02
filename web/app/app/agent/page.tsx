import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { AgentSettingsPanel } from "@/components/AgentSettingsPanel";
import { sessionTenantId } from "@/lib/tenant";

export default async function AgentSettingsPage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <>
      <PageHeader
        title="Agent settings"
        description="Manage your AI agent name, instructions, channel allowlist, and job schedules."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Agent" },
        ]} />
      <p>
        Register CLI and MCP tools on the{" "}
        <Link href="/app/tools">Tools</Link> page.
      </p>
      <div>
        <AgentSettingsPanel
          accessToken={session?.accessToken ?? null}
          tenantId={tenantId} />
      </div>
    </>
  );
}
