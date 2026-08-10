import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { OrgNav } from "@/components/OrgNav";
import { SlackConnectPanel } from "@/components/SlackConnectPanel";
import { sessionTenantId } from "@/lib/tenant";

type Props = {
  searchParams?: Promise<Record<string, string | string[] | undefined>> | Record<
    string,
    string | string[] | undefined
  >;
};

function param(
  value: string | string[] | undefined,
): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

export default async function SlackConnectPage({ searchParams }: Props) {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);
  const params = (await searchParams) ?? {};
  const connected = param(params.connected) === "1";
  const error = param(params.error) ?? null;

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif", maxWidth: 720 }}>
      <h1 style={{ marginTop: 0 }}>Slack</h1>
      <p>
        Connect your Slack workspace so the agent can join your team (OR-08).
      </p>
      <p>
        Signed in as {session?.user?.email} ({session?.user?.role}
        {tenantId ? ` · tenant ${tenantId}` : ""})
      </p>
      <SlackConnectPanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
        connectedFlag={connected}
        errorFlag={error}
      />
      <OrgNav current="slack" />
    </main>
  );
}
