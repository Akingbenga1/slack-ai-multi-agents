import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import panel from "@/components/dashboard/panel.module.css";
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
      <PageHeader title="Tenant access denied" />
      <div className={panel.section}>
        <p className={panel.error} role="alert">
          You cannot open another organisation&apos;s portal routes (OR-09). Your session is
          scoped to <code>{allowed || "(no tenant)"}</code>
          {pathTenant ? (
            <>
              ; requested <code>{pathTenant}</code>
            </>
          ) : null}
          .
        </p>
      </div>
    </>
  );
}
