import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { AdminDashboardShell } from "@/components/dashboard/AdminDashboardShell";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);

  return (
    <AdminDashboardShell
      userEmail={session?.user?.email ?? null}
      userRole={session?.user?.role ?? null}
    >
      {children}
    </AdminDashboardShell>
  );
}
