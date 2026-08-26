import { PageHeader } from "@/components/dashboard/PageHeader";
import { ToolsManagerPanel } from "@/components/tools/ToolsManagerPanel";

export default function OrgToolsPage() {
  return (
    <>
      <PageHeader
        title="Tools"
        description="Register CLI tools and MCP servers for your organisation's AI agent."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Tools" },
        ]}
      />
      <ToolsManagerPanel createHref="/app/tools/new" />
    </>
  );
}
