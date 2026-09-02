import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { PlatformHealthPanel } from "@/components/PlatformHealthPanel";

export default async function AdminHealthPage() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <PageHeader
        title="Platform health"
        description="Compose service probes, job failure rates, and usage activity across all tenants."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Platform health" },
        ]}
        className="mb-8"
      />
      <PlatformHealthPanel accessToken={session?.accessToken ?? null} />
    </>
  );
}
