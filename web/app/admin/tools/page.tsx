import Link from "next/link";
import { PageHeader } from "@/components/dashboard/PageHeader";
import panel from "@/components/dashboard/panel.module.css";
import { PlatformToolsOverviewPanel } from "@/components/tools/PlatformToolsOverviewPanel";

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
          <div className={panel.formRow}>
            <Link href="/admin/cli-host" className={panel.btnSecondary}>
              CLI host
            </Link>
            <Link href="/admin/mcp-host" className={panel.btnSecondary}>
              MCP host
            </Link>
            <Link href="/admin/tools/new" className={panel.btnPrimary}>
              New tool
            </Link>
          </div>
        }
      />
      <PlatformToolsOverviewPanel />
    </>
  );
}
