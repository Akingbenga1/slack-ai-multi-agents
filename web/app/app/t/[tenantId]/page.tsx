import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { sessionTenantId, tenantMatchesSession } from "@/lib/tenant";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

/**
 * Explicit tenant-scoped entry (Sprint 19.3).
 * Org A cannot open Org B's `/app/t/{id}` — mismatch shows forbidden.
 */
export default async function TenantScopedAppPage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const resolved = await params;
  const pathTenant = (resolved.tenantId || "").trim();
  const allowed = sessionTenantId(session?.user?.tenantId);

  if (tenantMatchesSession(allowed, pathTenant) && allowed) {
    redirect("/app");
  }

  return (
    <main style={{ padding: "0 2rem 2rem", fontFamily: "system-ui, sans-serif", maxWidth: 640 }}>
      <h1 style={{ marginTop: 0 }}>Tenant access denied</h1>
      <p role="alert" style={{ color: "#b00020" }}>
        You cannot open another organisation&apos;s portal routes (OR-09). Your
        session is scoped to{" "}
        <code>{allowed || "(no tenant)"}</code>
        {pathTenant ? (
          <>
            ; requested <code>{pathTenant}</code>
          </>
        ) : null}
        .
      </p>
    </main>
  );
}
