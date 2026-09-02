import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { sessionTenantId, tenantMatchesSession } from "@/lib/tenant";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function TenantScopedAppPage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const resolved = await params;
  const pathTenant = (resolved.tenantId || "").trim();
  const allowed = sessionTenantId(session?.user?.tenantId);

  if (tenantMatchesSession(allowed, pathTenant) && allowed) {
    redirect("/app");
  }

  return (
    <>
      <PageHeader
        className="mb-8"
        title="Tenant access denied"
        description="Your session is scoped to one organisation — you cannot open another tenant's portal routes."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Access denied" },
        ]}
      />
      <Card className="border-danger/30 bg-danger/5">
        <CardContent className="py-8">
          <p className="text-body-md text-foreground" role="alert">
            You cannot open another organisation&apos;s portal routes. Your session is scoped to{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 text-sm">{allowed || "(no tenant)"}</code>
            {pathTenant ? (
              <>
                ; requested{" "}
                <code className="rounded bg-muted px-1.5 py-0.5 text-sm">{pathTenant}</code>
              </>
            ) : null}
            .
          </p>
          <Link
            href="/app"
            className={cn(buttonVariants({ variant: "default" }), "mt-6 rounded-full")}
          >
            Back to overview
          </Link>
        </CardContent>
      </Card>
    </>
  );
}
