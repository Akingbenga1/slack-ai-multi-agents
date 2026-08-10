import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { AdminNav } from "@/components/AdminNav";
import { TenantListPanel } from "@/components/TenantListPanel";

export default async function AdminTenantsPage() {
  const session = await getServerSession(authOptions);

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif", maxWidth: 960 }}>
      <h1 style={{ marginTop: 0 }}>Tenants</h1>
      <p>Plan status, Slack connected, and last sync across organisations.</p>
      <TenantListPanel accessToken={session?.accessToken ?? null} />
      <AdminNav current="tenants" />
    </main>
  );
}
