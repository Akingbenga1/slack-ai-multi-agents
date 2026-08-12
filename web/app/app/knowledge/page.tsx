import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { KnowledgePanel } from "@/components/KnowledgePanel";
import { sessionTenantId } from "@/lib/tenant";

export default async function KnowledgePage() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <main style={{ padding: "0 2rem 2rem", fontFamily: "system-ui, sans-serif", maxWidth: 800 }}>
      <h1 style={{ marginTop: 0 }}>Knowledge</h1>
      <p>
        Upload documents or Slack history, watch ingest status, and trigger live
        Slack sync (OR-05 / OR-06).
      </p>
      <p>
        Signed in as {session?.user?.email} ({session?.user?.role}
        {tenantId ? ` · tenant ${tenantId}` : ""})
      </p>
      <KnowledgePanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
    </main>
  );
}
