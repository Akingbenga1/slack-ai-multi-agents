import Link from "next/link";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export default function AdminToolsPage() {
  return (
    <>
      <PageHeader
        title="Tools"
        description="Open a tenant to manage that organisation's MCP installs. Platform-wide MCP registry UI is not the near-term product surface."
        breadcrumbs={[
          { label: "Overview", href: "/admin" },
          { label: "Tools" },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link
              href="/admin/cli-host"
              className={cn(buttonVariants({ variant: "secondary" }))}
            >
              CLI host
            </Link>
            <Link
              href="/admin/tools/new"
              className={cn(buttonVariants({ variant: "default" }), "rounded-full")}
            >
              <Plus className="h-4 w-4" />
              New tool
            </Link>
          </div>
        }
        className="mb-8"
      />
      <Card>
        <CardHeader className="border-b border-border">
          <CardTitle className="text-headline-md">Tenant MCP installs</CardTitle>
          <CardDescription className="mt-1">
            Choose a tenant, then use its Tools page for named MCP connections
            (URL, Bearer, Connect, Available).
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6">
          <Link
            href="/admin/tenants"
            className={cn(buttonVariants({ variant: "default" }), "rounded-full")}
          >
            Open tenants
          </Link>
        </CardContent>
      </Card>
    </>
  );
}
