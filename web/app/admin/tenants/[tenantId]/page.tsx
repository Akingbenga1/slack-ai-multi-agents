import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { TenantDetailPanel } from "@/components/TenantDetailPanel";

type Props = {
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function AdminTenantDetailPage({ params }: Props) {
  const session = await getServerSession(authOptions);
  const resolved = await params;

  return (
    <TenantDetailPanel
      accessToken={session?.accessToken ?? null}
      tenantId={resolved.tenantId}
    />
  );
}
