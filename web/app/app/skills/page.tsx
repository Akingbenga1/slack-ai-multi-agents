import { getServerSession } from "next-auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { SkillsPanel } from "@/components/skills/SkillsPanel";
import { authOptions } from "@/lib/auth";
import { sessionTenantId } from "@/lib/tenant";

export default async function OrgSkillsPage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <>
      <PageHeader
        title="Skills"
        description="Create markdown skills and folders for your organisation's AI agent."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Skills" },
        ]}
        className="mb-8"
      />
      <SkillsPanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
    </>
  );
}
