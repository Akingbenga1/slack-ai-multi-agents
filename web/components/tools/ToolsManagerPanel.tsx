"use client";

import Link from "next/link";
import { useState } from "react";
import { Plus, Trash2, Wrench } from "lucide-react";
import {
  formatToolKind,
  getMockTools,
  type MockTool,
} from "@/lib/mock/tools-data";
import { TenantMcpServersPanel } from "@/components/tools/TenantMcpServersPanel";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  tenantLabel?: string;
  createHref: string;
  accessToken?: string | null;
  tenantId?: string | null;
};

function toolKindVariant(
  kind: string,
): "default" | "success" | "warning" | "muted" {
  const value = kind.toLowerCase();
  if (value === "mcp") return "default";
  if (value === "cli") return "success";
  if (value === "http") return "warning";
  return "muted";
}

export function ToolsManagerPanel({
  tenantLabel,
  createHref,
  accessToken = null,
  tenantId = null,
}: Props) {
  const [tools, setTools] = useState<MockTool[]>(() => getMockTools());
  const [message, setMessage] = useState<string | null>(null);

  function removeTool(name: string) {
    setTools((prev) => prev.filter((t) => t.name !== name));
    setMessage(`Removed tool "${name}".`);
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between gap-3">
              <p className="text-label-md text-muted-foreground">Registered tools</p>
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                <Wrench className="h-4 w-4" />
              </div>
            </div>
            <p className="mt-3 text-headline-md text-foreground">{tools.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between gap-3">
              <p className="text-label-md text-muted-foreground">MCP (tenant)</p>
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                <Wrench className="h-4 w-4" />
              </div>
            </div>
            <p className="mt-3 text-body-md text-muted-foreground">
              Managed below via live tenant API
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle className="text-headline-md">Tool registry</CardTitle>
              <CardDescription className="mt-1">
                {tenantLabel
                  ? `CLI tools and MCP servers available to ${tenantLabel}'s agent.`
                  : "CLI tools and MCP servers available to the agent."}
              </CardDescription>
            </div>
            <Link
              href={createHref}
              className={cn(buttonVariants({ variant: "default" }), "rounded-full")}
            >
              <Plus className="h-4 w-4" />
              New tool
            </Link>
          </div>
        </CardHeader>
        {message ? (
          <CardContent className="border-b border-border pt-6">
            <p
              className="rounded-lg border border-success/20 bg-success-muted px-4 py-3 text-body-md text-success"
              role="status"
            >
              {message}
            </p>
          </CardContent>
        ) : null}
      </Card>

      <TenantMcpServersPanel accessToken={accessToken} tenantId={tenantId} />

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-6 py-5">
          <div>
            <h2 className="text-headline-md text-foreground">Registered tools</h2>
            <p className="mt-1 text-body-md text-muted-foreground">
              Tool catalog entries (still local mock until wired separately).
            </p>
          </div>
          {tools.length > 0 ? <Badge variant="muted">{tools.length}</Badge> : null}
        </div>
        <CardContent className="px-0 pb-0 pt-0">
          {tools.length === 0 ? (
            <div className="px-6 py-10 text-center">
              <p className="text-body-md text-muted-foreground">
                No tools registered yet.
              </p>
              <Link
                href={createHref}
                className={cn(
                  buttonVariants({ variant: "default" }),
                  "mt-4 inline-flex rounded-full",
                )}
              >
                <Plus className="h-4 w-4" />
                Create first tool
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border bg-[#f8fafc]">
                    <th className="px-6 py-3 text-label-md text-muted-foreground">
                      Name
                    </th>
                    <th className="px-4 py-3 text-label-md text-muted-foreground">
                      Kind
                    </th>
                    <th className="px-4 py-3 text-label-md text-muted-foreground">
                      Description
                    </th>
                    <th className="px-4 py-3 text-label-md text-muted-foreground">
                      Config
                    </th>
                    <th className="px-6 py-3 text-right text-label-md text-muted-foreground">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {tools.map((tool) => (
                    <tr
                      key={tool.id}
                      className="border-b border-border last:border-b-0 hover:bg-muted/40"
                    >
                      <td className="px-6 py-3">
                        <p className="font-medium text-foreground">{tool.name}</p>
                        {tool.mcpServerName ? (
                          <p className="mt-1 text-xs text-muted-foreground">
                            via {tool.mcpServerName}
                          </p>
                        ) : null}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={toolKindVariant(tool.kind)}>
                          {formatToolKind(tool.kind)}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {tool.description || "—"}
                      </td>
                      <td className="px-4 py-3 text-sm text-foreground">
                        {tool.configSummary}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeTool(tool.name)}
                          className="text-danger hover:text-danger"
                        >
                          <Trash2 className="h-4 w-4" />
                          Remove
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
