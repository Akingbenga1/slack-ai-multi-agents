import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { TenantListPanel } from "@/components/TenantListPanel";

export default async function AdminTenantsPage() {
  const session = await getServerSession(authOptions);

  return (
    <main style={{ padding: "0 2rem 2rem", fontFamily: "system-ui, sans-serif", maxWidth: 960 }}>
      <h1 style={{ marginTop: 0 }}>Tenants</h1>
      <p>Plan status, Slack connected, and last sync across organisations.</p>
      <TenantListPanel accessToken={session?.accessToken ?? null} />
    </main>
  );
}
