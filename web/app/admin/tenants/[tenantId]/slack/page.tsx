import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { SlackConnectPanel } from "@/components/SlackConnectPanel";
import { getMockTenantBilling } from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
  searchParams?: Promise<Record<string, string | string[] | undefined>> | Record<
    string,
    string | string[] | undefined>;
};

function param(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

export default async function AdminTenantSlackPage({ params, searchParams }: Props) {
  const session = await getServerSession(authOptions);
  const { tenantId } = await params;
  const tenantName = getMockTenantBilling(tenantId).tenantName;
  const resolvedParams = (await searchParams) ?? {};
  const connected = param(resolvedParams.connected) === "1";
  const error = param(resolvedParams.error) ?? null;

  return (
    <>
      <PageHeader
        title="Slack"
        description={`Slack workspace connection for ${tenantName}.`}
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: tenantName, href: `/admin/tenants/${tenantId}` },
          { label: "Slack" },
        ]}
        className="mb-8"
      />
      <SlackConnectPanel
          accessToken={session?.accessToken ?? null}
          tenantId={tenantId}
          connectedFlag={connected}
          errorFlag={error}
        />
    </>
  );
}
