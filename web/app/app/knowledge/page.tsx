import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { KnowledgePanel } from "@/components/KnowledgePanel";
import { sessionTenantId } from "@/lib/tenant";

export default async function KnowledgePage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <>
      <PageHeader
        title="Knowledge"
        description="Upload documents or Slack history, watch ingest status, browse tenant files, and trigger live Slack sync."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Knowledge" },
        ]} />
      <div>
        <KnowledgePanel
          accessToken={session?.accessToken ?? null}
          tenantId={tenantId} />
      </div>
    </>
  );
}
