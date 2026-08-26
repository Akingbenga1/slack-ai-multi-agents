import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { TenantCreateForm } from "@/components/TenantCreateForm";

export default async function AdminTenantCreatePage() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <PageHeader
        title="New tenant"
        description="Provision a new organisation with org admin, billing row, and default agent config."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tenants", href: "/admin/tenants" },
          { label: "New" },
        ]}
      />
      <TenantCreateForm accessToken={session?.accessToken ?? null} />
    </>
  );
}
