import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { AdminNav } from "@/components/AdminNav";
import { TenantDetailPanel } from "@/components/TenantDetailPanel";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantDetailPage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const resolved = await params;

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif", maxWidth: 720 }}>
      <h1 style={{ marginTop: 0 }}>Tenant detail</h1>
      <TenantDetailPanel
        accessToken={session?.accessToken ?? null}
        tenantId={resolved.tenantId}
      />
      <AdminNav current="tenants" />
    </main>
  );
}
