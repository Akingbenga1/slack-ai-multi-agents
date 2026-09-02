import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { AdminTenantsPageContent } from "@/components/admin/AdminTenantsPageContent";

export default async function AdminTenantsPage() {
  const session = await getServerSession(authOptions);

  return <AdminTenantsPageContent accessToken={session?.accessToken ?? null} />;
}
