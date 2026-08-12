import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";

export default async function AdminHome() {
  const session = await getServerSession(authOptions);

  return (
    <main style={{ padding: "0 2rem 2rem", fontFamily: "system-ui, sans-serif", maxWidth: 900 }}>
      <h1 style={{ marginTop: 0 }}>Platform admin</h1>
      <p>
        Cross-tenant oversight — plan status, Slack connection, sync health, and
        support actions (PO-01 / PO-25 / PO-13).
      </p>
      <p>
        Signed in as {session?.user?.email} ({session?.user?.role})
      </p>
      <ul style={{ lineHeight: 1.7 }}>
        <li>
          <Link href="/admin/tenants">Tenants</Link> — list + detail (plan, Slack,
          last sync)
        </li>
        <li>
          <Link href="/admin/health">Health</Link> — Compose services + error rates
        </li>
      </ul>
    </main>
  );
}
