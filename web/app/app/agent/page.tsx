import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { AgentSettingsPanel } from "@/components/AgentSettingsPanel";
import { OrgNav } from "@/components/OrgNav";
import { sessionTenantId } from "@/lib/tenant";

export default async function AgentSettingsPage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif", maxWidth: 720 }}>
      <h1 style={{ marginTop: 0 }}>Agent settings</h1>
      <p>
        Manage your AI agent name, instructions, channel allowlist, and job
        schedules (OR-03 / OR-04).
      </p>
      <p>
        Signed in as {session?.user?.email} ({session?.user?.role}
        {tenantId ? ` · tenant ${tenantId}` : ""})
      </p>
      <AgentSettingsPanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
      <OrgNav current="agent" />
    </main>
  );
}
