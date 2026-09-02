import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { InvitePanel } from "@/components/InvitePanel";
import { PublicAuthFooterLink, PublicAuthShell } from "@/components/auth/PublicAuthShell";
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

export default async function InviteAcceptPage({ searchParams }: Props) {
  const session = await getServerSession(authOptions);
  const params = (await searchParams) ?? {};
  const token = param(params.token) || null;
  const tenantId = sessionTenantId(session?.user?.tenantId);
  const isOrgAdmin = session?.user?.role === "org_admin";

  if (!token && isOrgAdmin) {
    redirect("/app/invite");
  }

  const footer = token ? (
    <>
      Wrong page? <PublicAuthFooterLink href="/login">Sign in</PublicAuthFooterLink>
    </>
  ) : isOrgAdmin ? (
    <>
      <PublicAuthFooterLink href="/app/team">Manage team</PublicAuthFooterLink>
      {" · "}
      <PublicAuthFooterLink href="/app">Org portal</PublicAuthFooterLink>
    </>
  ) : (
    <>
      Have an invite link? Open it in your browser. Otherwise{" "}
      <PublicAuthFooterLink href="/login">sign in</PublicAuthFooterLink>
      {" or "}
      <PublicAuthFooterLink href="/signup">create an organisation</PublicAuthFooterLink>.
    </>
  );

  return (
    <PublicAuthShell
      title={token ? "Accept invitation" : "Team invitation"}
      description={
        token
          ? "Set your password to join the organisation you were invited to."
          : "Use the invitation link you received from your organisation admin."
      }
      maxWidth="lg"
      footer={footer}
    >
      <InvitePanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
        inviteToken={token}
        isOrgAdmin={!!isOrgAdmin}
      />
    </PublicAuthShell>
  );
}
