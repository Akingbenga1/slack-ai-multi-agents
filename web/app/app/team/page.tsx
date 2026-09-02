import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { TeamPanel } from "@/components/TeamPanel";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { sessionTenantId } from "@/lib/tenant";

export default async function OrgTeamPage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);
  const isOrgAdmin = session?.user?.role === "org_admin";

  return (
    <>
      <PageHeader
        className="mb-8"
        title="Team"
        description="View members, manage pending invites, and grant org-admin access."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Team" },
        ]}
      />
      {isOrgAdmin && session?.accessToken ? (
        <TeamPanel
          accessToken={session.accessToken}
          tenantId={tenantId}
          currentUserId={session.user?.id ?? null}
        />
      ) : (
        <Card>
          <CardContent className="py-10 text-center">
            <p className="text-body-md text-muted-foreground">
              Sign in as an org admin to manage team access.
            </p>
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "default" }), "mt-4 rounded-full")}
            >
              Sign in
            </Link>
          </CardContent>
        </Card>
      )}
    </>
  );
}
