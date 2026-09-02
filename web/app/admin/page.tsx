import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { AdminOverviewDashboard } from "@/components/admin/AdminOverviewDashboard";
import { PageHeader } from "@/components/dashboard/PageHeader";

export default async function AdminHome() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <PageHeader
        title="Overview"
        description="Cross-tenant oversight — plan status, Slack connections, sync health, and support actions."
      />
      <AdminOverviewDashboard accessToken={session?.accessToken ?? null} />
    </>
  );
}
