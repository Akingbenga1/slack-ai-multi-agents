import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { TenantListPanel } from "@/components/TenantListPanel";

export default async function AdminTenantsPage() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <PageHeader
        title="Tenants"
        description="Browse organisations — click a name for details, use the row menu for billing and access actions."
      />
      <TenantListPanel accessToken={session?.accessToken ?? null} />
    </>
  );
}
