import Link from "next/link";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { PlatformToolsOverviewPanel } from "@/components/tools/PlatformToolsOverviewPanel";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function AdminToolsPage() {
  return (
    <>
      <PageHeader
        title="Tools"
        description="Cross-tenant tool and MCP server registry — per-tenant CLI and MCP configuration."
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
              href="/admin/mcp-host"
              className={cn(buttonVariants({ variant: "secondary" }))}
            >
              MCP host
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
      <PlatformToolsOverviewPanel />
    </>
  );
}
