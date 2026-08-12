import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { WorkflowsPanel } from "@/components/WorkflowsPanel";
import { sessionTenantId } from "@/lib/tenant";

export default async function WorkflowsPage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <main
      style={{
        padding: "0 2rem 2rem",
        fontFamily: "system-ui, sans-serif",
        maxWidth: 800,
      }}
    >
      <h1 style={{ marginTop: 0 }}>Workflow library</h1>
      <p>
        Shared workflow templates from Slack channel uploads. Colleagues can
        copy a template into a personal draft and edit their own version
        (TM-20 / TM-21). Ask the Slack agent to advise on a stored or attached
        workflow for grounded operationalisation tips (TM-22).
      </p>
      <p>
        Signed in as {session?.user?.email} ({session?.user?.role}
        {tenantId ? ` · tenant ${tenantId}` : ""})
      </p>
      <WorkflowsPanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
    </main>
  );
}
