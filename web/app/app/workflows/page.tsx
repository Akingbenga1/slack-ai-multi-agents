import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import panel from "@/components/dashboard/panel.module.css";
import { WorkflowsPanel } from "@/components/WorkflowsPanel";
import { sessionTenantId } from "@/lib/tenant";

export default async function WorkflowsPage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <>
      <PageHeader
        title="Workflow library"
        description="Shared workflow templates from Slack. Copy a template into a personal draft and edit your own version."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Workflows" },
        ]}
      />
      <div className={panel.section}>
        <WorkflowsPanel
          accessToken={session?.accessToken ?? null}
          tenantId={tenantId}
        />
      </div>
    </>
  );
}
