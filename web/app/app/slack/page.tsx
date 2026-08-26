import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import panel from "@/components/dashboard/panel.module.css";
import { SlackConnectPanel } from "@/components/SlackConnectPanel";
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

export default async function SlackConnectPage({ searchParams }: Props) {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);
  const params = (await searchParams) ?? {};
  const connected = param(params.connected) === "1";
  const error = param(params.error) ?? null;

  return (
    <>
      <PageHeader
        title="Slack"
        description="Connect your Slack workspace so the agent can join your team."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Slack" },
        ]}
      />
      <div className={panel.section}>
        <SlackConnectPanel
          accessToken={session?.accessToken ?? null}
          tenantId={tenantId}
          connectedFlag={connected}
          errorFlag={error}
        />
      </div>
    </>
  );
}
