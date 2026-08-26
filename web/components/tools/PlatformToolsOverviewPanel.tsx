import Link from "next/link";
import panel from "@/components/dashboard/panel.module.css";
import { getMockPlatformToolsOverview } from "@/lib/mock/tools-data";

export function PlatformToolsOverviewPanel() {
  const rows = getMockPlatformToolsOverview();
  const totalTools = rows.reduce((sum, r) => sum + r.toolCount, 0);
  const totalMcp = rows.reduce((sum, r) => sum + r.mcpServerCount, 0);

  return (
    <>
      <div className={panel.metrics}>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>Tools</p>
          <p className={panel.metricValue}>{totalTools}</p>
        </div>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>MCP servers</p>
          <p className={panel.metricValue}>{totalMcp}</p>
        </div>
        <div className={panel.metric}>
          <p className={panel.metricLabel}>Tenants</p>
          <p className={panel.metricValue}>{rows.length}</p>
        </div>
      </div>

      <section className={panel.section}>
        <div className={panel.sectionHeader}>
          <h2 className={panel.sectionTitle}>Tools by tenant</h2>
          <span className={panel.sectionCount}>{rows.length}</span>
        </div>
        <p className={panel.sectionDesc}>
          Open a tenant to register CLI tools, MCP servers, and tool metadata.
        </p>
        <div className={panel.tableWrap}>
          <table className={panel.table}>
            <thead>
              <tr>
                <th scope="col">Tenant</th>
                <th scope="col">Tools</th>
                <th scope="col">MCP servers</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.tenantId}>
                  <td>
                    <Link
                      href={`/admin/tenants/${row.tenantId}/tools`}
                      className={panel.tableLink}
                    >
                      {row.tenantName}
                    </Link>
                    <div className={panel.tableMuted}>{row.tenantSlug}</div>
                  </td>
                  <td>{row.toolCount}</td>
                  <td>{row.mcpServerCount}</td>
                  <td>
                    <Link href={`/admin/tenants/${row.tenantId}/tools`}>Manage</Link>
                    {" · "}
                    <Link href={`/admin/tenants/${row.tenantId}/tools/new`}>New tool</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
