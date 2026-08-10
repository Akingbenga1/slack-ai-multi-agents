import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { OrgNav } from "@/components/OrgNav";
import { UsageSummaryPanel } from "@/components/UsageSummaryPanel";
import { sessionTenantId } from "@/lib/tenant";

export default async function UsagePage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif", maxWidth: 720 }}>
      <h1 style={{ marginTop: 0 }}>Logs &amp; usage</h1>
      <p>
        Mentions, jobs, errors, and token usage for your organisation (OR-07).
      </p>
      <p>
        Signed in as {session?.user?.email} ({session?.user?.role}
        {tenantId ? ` · tenant ${tenantId}` : ""})
      </p>
      <UsageSummaryPanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
      <OrgNav current="usage" />
    </main>
  );
}
