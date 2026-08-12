import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PlatformHealthPanel } from "@/components/PlatformHealthPanel";

export default async function AdminHealthPage() {
  const session = await getServerSession(authOptions);

  return (
    <main style={{ padding: "0 2rem 2rem", fontFamily: "system-ui, sans-serif", maxWidth: 720 }}>
      <h1 style={{ marginTop: 0 }}>Platform health</h1>
      <p>Compose probes and recent job / usage rates (PO-13).</p>
      <PlatformHealthPanel accessToken={session?.accessToken ?? null} />
    </main>
  );
}
