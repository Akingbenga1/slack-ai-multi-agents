import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { OrgDashboardShell } from "@/components/dashboard/OrgDashboardShell";

export default async function OrgAppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);

  return (
    <OrgDashboardShell
      userEmail={session?.user?.email ?? null}
      userRole={session?.user?.role ?? null}
    >
      {children}
    </OrgDashboardShell>
  );
}
