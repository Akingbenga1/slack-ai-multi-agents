import { PageHeader } from "@/components/dashboard/PageHeader";
import { OrgInviteRedirect } from "@/components/auth/OrgInviteRedirect";

export default function OrgInviteRedirectPage() {
  return (
    <>
      <PageHeader
        className="mb-8"
        title="Team invites"
        description="Redirecting to team management where you can invite org admins."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Team" },
        ]}
      />
      <OrgInviteRedirect />
    </>
  );
}
