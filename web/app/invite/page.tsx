import Link from "next/link";
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

export default async function InvitePage({ searchParams }: Props) {
  const session = await getServerSession(authOptions);
  const params = (await searchParams) ?? {};
  const token = param(params.token) || null;
  const tenantId = sessionTenantId(session?.user?.tenantId);
  const isOrgAdmin = session?.user?.role === "org_admin";

  return (
    <main
      style={{
        padding: "2rem",
        fontFamily: "system-ui, sans-serif",
        maxWidth: 640,
      }}
    >
      <h1 style={{ marginTop: 0 }}>Invite / membership</h1>
      <p>
        An <strong>org_admin</strong> belongs to exactly one tenant. A{" "}
        <strong>platform_owner</strong> has all-access and no tenant membership
        row.
      </p>
      <InvitePanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
        inviteToken={token}
        isOrgAdmin={!!isOrgAdmin}
      />
      <p style={{ marginTop: "1.5rem" }}>
        <Link href="/app">Org portal</Link> · <Link href="/login">Login</Link> ·{" "}
        <Link href="/signup">Signup</Link>
      </p>
    </main>
  );
}
