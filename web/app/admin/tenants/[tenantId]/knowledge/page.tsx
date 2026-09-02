import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { KnowledgePanel } from "@/components/KnowledgePanel";
import { getMockTenantBilling } from "@/lib/mock/billing-data";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantKnowledgePage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const { tenantId } = await params;
  const tenantName = getMockTenantBilling(tenantId).tenantName;

  return (
    <>
      <PageHeader
        title="Knowledge"
        description={`Uploads, ingest jobs, tenant files, and Slack sync for ${tenantName}.`}
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: tenantName, href: `/admin/tenants/${tenantId}` },
          { label: "Knowledge" },
        ]}
        className="mb-8"
      />
      <KnowledgePanel
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
        slackHref={`/admin/tenants/${tenantId}/slack`}
      />
    </>
  );
}
