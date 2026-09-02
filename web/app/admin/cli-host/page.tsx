import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { AdminCliHostPanel } from "@/components/admin/AdminCliHostPanel";
import { buttonVariants } from "@/components/ui/button";

export default async function AdminCliHostPage() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <PageHeader
        title="CLI host"
        description="Check whether registered CLI tools are on this machine, and optionally install them before the executor runs."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tools", href: "/admin/tools" },
          { label: "CLI host" },
        ]}
        actions={
          <Link
            href="/admin/tools"
            className={buttonVariants({ variant: "secondary" })}
          >
            All tools
          </Link>
        }
        className="mb-8"
      />
      <AdminCliHostPanel accessToken={session?.accessToken ?? null} />
    </>
  );
}
