import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { InvitePanel } from "@/components/InvitePanel";
import { sessionTenantId } from "@/lib/tenant";

type Props = {
  searchParams?: Promise<Record<string, string | string[] | undefined>> | Record<
    string,
    string | string[] | undefined
  >;
};

function param(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

/** Public accept URL (`/invite?token=…`). Create-invite UI lives under `/app/invite`. */
export default async function InviteAcceptPage({ searchParams }: Props) {
  const session = await getServerSession(authOptions);
  const params = (await searchParams) ?? {};
  const token = param(params.token) || null;
  const tenantId = sessionTenantId(session?.user?.tenantId);
  const isOrgAdmin = session?.user?.role === "org_admin";

  if (!token && isOrgAdmin) {
    redirect("/app/invite");
  }

  return (
    <main
      style={{
        padding: "2rem",
        fontFamily: "system-ui, sans-serif",
        maxWidth: 640,
        margin: "0 auto",
      }}
    >
      <h1 style={{ marginTop: 0 }}>{token ? "Accept invite" : "Invite / membership"}</h1>
      {!token ? (
        <p>
          Org admins invite teammates from the portal. Open a magic-link invite you were
          given, or sign in to create one.
        </p>
      ) : (
        <p>Join the organisation you were invited to. This does not create a new organisation.</p>
      )}
      <InvitePanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
        inviteToken={token}
        isOrgAdmin={!!isOrgAdmin}
      />
      <p style={{ marginTop: "1.5rem" }}>
        <Link href="/app">Org portal</Link> · <Link href="/login">Login</Link> ·{" "}
        <Link href="/signup">Signup</Link>
        {isOrgAdmin ? (
          <>
            {" · "}
            <Link href="/app/invite">Invite team</Link>
          </>
        ) : null}
      </p>
    </main>
  );
}
