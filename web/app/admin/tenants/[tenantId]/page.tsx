import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { TenantDetailPanel } from "@/components/TenantDetailPanel";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantDetailPage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const resolved = await params;

  return (
    <>
      <PageHeader
        title="Tenant detail"
        description="Plan, Slack connection, sync status, and support actions for this organisation."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: "Detail" },
        ]}
      />
      <TenantDetailPanel
        accessToken={session?.accessToken ?? null}
        tenantId={resolved.tenantId}
      />
    </>
  );
}
