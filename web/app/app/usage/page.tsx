import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import panel from "@/components/dashboard/panel.module.css";
import { UsageSummaryPanel } from "@/components/UsageSummaryPanel";
import { sessionTenantId } from "@/lib/tenant";

export default async function UsagePage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <>
      <PageHeader
        title="Logs & usage"
        description="Mentions, jobs, errors, and token usage for your organisation."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Usage" },
        ]}
      />
      <div className={panel.section}>
        <UsageSummaryPanel
          accessToken={session?.accessToken ?? null}
          tenantId={tenantId}
        />
      </div>
    </>
  );
}
