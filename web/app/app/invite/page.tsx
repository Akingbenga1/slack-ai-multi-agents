import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import panel from "@/components/dashboard/panel.module.css";
import { InvitePanel } from "@/components/InvitePanel";
import { sessionTenantId } from "@/lib/tenant";

export default async function OrgInvitePage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);
  const isOrgAdmin = session?.user?.role === "org_admin";

  return (
    <>
      <PageHeader
        title="Invite team"
        description="Invite another org admin to this organisation with a copyable magic link."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Invite team" },
        ]}
      />
      <section className={panel.section}>
        <InvitePanel
          accessToken={session?.accessToken ?? null}
          tenantId={tenantId}
          inviteToken={null}
          isOrgAdmin={!!isOrgAdmin}
        />
      </section>
    </>
  );
}
