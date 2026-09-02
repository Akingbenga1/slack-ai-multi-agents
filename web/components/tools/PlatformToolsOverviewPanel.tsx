import Link from "next/link";
import { Plus, Server, Users, Wrench } from "lucide-react";
import { getMockPlatformToolsOverview } from "@/lib/mock/tools-data";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function PlatformToolsOverviewPanel() {
  const rows = getMockPlatformToolsOverview();
  const totalTools = rows.reduce((sum, r) => sum + r.toolCount, 0);
  const totalMcp = rows.reduce((sum, r) => sum + r.mcpServerCount, 0);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between gap-3">
              <p className="text-label-md text-muted-foreground">Tools</p>
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                <Wrench className="h-4 w-4" />
              </div>
            </div>
            <p className="mt-3 text-headline-md text-foreground">{totalTools}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between gap-3">
              <p className="text-label-md text-muted-foreground">MCP servers</p>
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                <Server className="h-4 w-4" />
              </div>
            </div>
            <p className="mt-3 text-headline-md text-foreground">{totalMcp}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between gap-3">
              <p className="text-label-md text-muted-foreground">Tenants</p>
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                <Users className="h-4 w-4" />
              </div>
            </div>
            <p className="mt-3 text-headline-md text-foreground">{rows.length}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-6 py-5">
          <div>
            <h2 className="text-headline-md text-foreground">Tools by tenant</h2>
            <p className="mt-1 text-body-md text-muted-foreground">
              Open a tenant to register CLI tools, MCP servers, and tool metadata.
            </p>
          </div>
          <Badge variant="muted">{rows.length}</Badge>
        </div>
        <CardContent className="px-0 pb-0 pt-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-border bg-[#f8fafc]">
                  <th scope="col" className="px-6 py-3 text-label-md text-muted-foreground">
                    Tenant
                  </th>
                  <th scope="col" className="px-4 py-3 text-label-md text-muted-foreground">
                    Tools
                  </th>
                  <th scope="col" className="px-4 py-3 text-label-md text-muted-foreground">
                    MCP servers
                  </th>
                  <th scope="col" className="px-6 py-3 text-right text-label-md text-muted-foreground">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.tenantId}
                    className="border-b border-border last:border-b-0 hover:bg-muted/40"
                  >
                    <td className="px-6 py-3">
                      <Link
                        href={`/admin/tenants/${row.tenantId}/tools`}
                        className="font-medium text-primary hover:underline"
                      >
                        {row.tenantName}
                      </Link>
                      <p className="mt-1 text-xs text-muted-foreground">{row.tenantSlug}</p>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{row.toolCount}</td>
                    <td className="px-4 py-3 text-muted-foreground">{row.mcpServerCount}</td>
                    <td className="px-6 py-3 text-right">
                      <div className="flex flex-wrap justify-end gap-2">
                        <Link
                          href={`/admin/tenants/${row.tenantId}/tools`}
                          className={cn(buttonVariants({ variant: "secondary", size: "sm" }))}
                        >
                          Manage
                        </Link>
                        <Link
                          href={`/admin/tenants/${row.tenantId}/tools/new`}
                          className={cn(
                            buttonVariants({ variant: "default", size: "sm" }),
                            "rounded-full",
                          )}
                        >
                          <Plus className="h-3.5 w-3.5" />
                          New tool
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
