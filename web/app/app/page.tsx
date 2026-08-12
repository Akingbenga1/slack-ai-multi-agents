import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PortalStatusBanners } from "@/components/PortalStatusBanners";
import { sessionTenantId } from "@/lib/tenant";

export default async function OrgAppHome() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <main style={{ padding: "0 2rem 2rem", fontFamily: "system-ui, sans-serif", maxWidth: 720 }}>
      <h1 style={{ marginTop: 0 }}>Organisation portal</h1>
      <p>
        Configure your agent, upload knowledge, and review usage — without waiting
        on the platform owner.
      </p>
      <p>
        Signed in as {session?.user?.email} ({session?.user?.role}
        {tenantId ? ` · tenant ${tenantId}` : ""})
      </p>
      <PortalStatusBanners
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
      <ul style={{ lineHeight: 1.7 }}>
        <li>
          <Link href="/app/agent">Agent settings</Link> — name, prompt, allowlist,
          schedules
        </li>
        <li>
          <Link href="/app/knowledge">Knowledge</Link> — uploads, ingest status,
          Slack sync
        </li>
        <li>
          <Link href="/app/workflows">Workflows</Link> — shared library from
          Slack (copy / draft)
        </li>
        <li>
          <Link href="/app/billing">Billing</Link> — pay / manage subscription
        </li>
        <li>
          <Link href="/app/usage">Usage</Link> — mentions, jobs, tokens, budgets
        </li>
        <li>
          <Link href="/app/slack">Slack</Link> — connect workspace / status
        </li>
      </ul>
    </main>
  );
}
