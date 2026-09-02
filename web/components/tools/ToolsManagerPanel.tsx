"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { Plus, Server, Trash2, Wrench } from "lucide-react";
import {
  createMockMcpServer,
  formatToolKind,
  getMockMcpServers,
  getMockTools,
  type MockMcpServer,
  type MockTool,
} from "@/lib/mock/tools-data";
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
};

const inputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

function toolKindVariant(
  kind: string,
): "default" | "success" | "warning" | "muted" {
  const value = kind.toLowerCase();
  if (value === "mcp") return "default";
  if (value === "cli") return "success";
  if (value === "http") return "warning";
  return "muted";
}

export function ToolsManagerPanel({ tenantLabel, createHref }: Props) {
  const [tools, setTools] = useState<MockTool[]>(() => getMockTools());
  const [mcpServers, setMcpServers] = useState<MockMcpServer[]>(() =>
    getMockMcpServers(),
  );
  const [message, setMessage] = useState<string | null>(null);

  const [showMcpForm, setShowMcpForm] = useState(false);
  const [mcpName, setMcpName] = useState("");
  const [mcpTransport, setMcpTransport] = useState<"stdio" | "http">("stdio");
  const [mcpCommand, setMcpCommand] = useState("python -m mcp_server");
  const [mcpUrl, setMcpUrl] = useState("");
  const [mcpEnabled, setMcpEnabled] = useState(true);

  function resetMcpForm() {
    setMcpName("");
    setMcpTransport("stdio");
    setMcpCommand("python -m mcp_server");
    setMcpUrl("");
    setMcpEnabled(true);
    setShowMcpForm(false);
  }

  function onAddMcpServer(ev: FormEvent) {
    ev.preventDefault();
    const name = mcpName.trim();
    if (!name) return;
    if (mcpServers.some((s) => s.name === name)) {
      setMessage(`MCP server "${name}" already exists.`);
      return;
    }
    const row = createMockMcpServer({
      name,
      transport: mcpTransport,
      command: mcpCommand,
      url: mcpUrl,
      enabled: mcpEnabled,
    });
    setMcpServers((prev) => [row, ...prev]);
    setMessage(`Added MCP server "${row.name}".`);
    resetMcpForm();
  }

  function removeTool(name: string) {
    setTools((prev) => prev.filter((t) => t.name !== name));
    setMessage(`Removed tool "${name}".`);
  }

  function removeMcpServer(id: string) {
    setMcpServers((prev) => prev.filter((s) => s.id !== id));
    setTools((prev) => prev.filter((t) => t.mcpServerId !== id));
    setMessage("Removed MCP server.");
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
              <p className="text-label-md text-muted-foreground">MCP servers</p>
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                <Server className="h-4 w-4" />
              </div>
            </div>
            <p className="mt-3 text-headline-md text-foreground">
              {mcpServers.length}
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
            <div className="flex flex-wrap gap-2">
              <Link
                href={createHref}
                className={cn(buttonVariants({ variant: "default" }), "rounded-full")}
              >
                <Plus className="h-4 w-4" />
                New tool
              </Link>
              <Button
                type="button"
                variant="secondary"
                className="rounded-full"
                onClick={() => setShowMcpForm((open) => !open)}
              >
                <Server className="h-4 w-4" />
                {showMcpForm ? "Cancel MCP form" : "Add MCP server"}
              </Button>
            </div>
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

      {showMcpForm ? (
        <Card>
          <CardHeader className="border-b border-border">
            <CardTitle className="text-headline-md">New MCP server</CardTitle>
            <CardDescription>
              Register a local stdio process or remote HTTP MCP endpoint before
              adding MCP-kind tools.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <form
              onSubmit={(ev) => void onAddMcpServer(ev)}
              className="grid max-w-2xl gap-4"
            >
              <label className="block">
                <span className="text-sm font-medium text-foreground">
                  Server name
                </span>
                <span className="mt-1 block text-sm text-muted-foreground">
                  Unique per tenant — e.g. bundled, github, custom
                </span>
                <input
                  value={mcpName}
                  onChange={(ev) => setMcpName(ev.target.value)}
                  required
                  className={cn(inputClassName, "mt-2")}
                />
              </label>

              <label className="block">
                <span className="text-sm font-medium text-foreground">Transport</span>
                <select
                  value={mcpTransport}
                  onChange={(ev) =>
                    setMcpTransport(ev.target.value as "stdio" | "http")
                  }
                  className={cn(inputClassName, "mt-2")}
                >
                  <option value="stdio">stdio (local process)</option>
                  <option value="http">http (remote server)</option>
                </select>
              </label>

              {mcpTransport === "stdio" ? (
                <label className="block">
                  <span className="text-sm font-medium text-foreground">
                    Launch command
                  </span>
                  <input
                    value={mcpCommand}
                    onChange={(ev) => setMcpCommand(ev.target.value)}
                    placeholder="python -m mcp_server"
                    required
                    className={cn(inputClassName, "mt-2 font-mono text-[13px]")}
                  />
                </label>
              ) : (
                <label className="block">
                  <span className="text-sm font-medium text-foreground">
                    Server URL
                  </span>
                  <input
                    type="url"
                    value={mcpUrl}
                    onChange={(ev) => setMcpUrl(ev.target.value)}
                    placeholder="https://mcp.example.com/sse"
                    required
                    className={cn(inputClassName, "mt-2 font-mono text-[13px]")}
                  />
                </label>
              )}

              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={mcpEnabled}
                  onChange={(ev) => setMcpEnabled(ev.target.checked)}
                  className="h-4 w-4 rounded border-border"
                />
                Enabled — agent can discover tools from this server
              </label>

              <div className="flex flex-wrap gap-2">
                <Button type="submit" className="rounded-full">
                  Save MCP server
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={resetMcpForm}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-6 py-5">
          <div>
            <h2 className="text-headline-md text-foreground">MCP servers</h2>
            <p className="mt-1 text-body-md text-muted-foreground">
              Connected MCP processes or HTTP endpoints.
            </p>
          </div>
          {mcpServers.length > 0 ? (
            <Badge variant="muted">{mcpServers.length}</Badge>
          ) : null}
        </div>
        <CardContent className="px-0 pb-0 pt-0">
          {mcpServers.length === 0 ? (
            <p className="px-6 py-8 text-center text-body-md text-muted-foreground">
              No MCP servers yet — add one to expose MCP tools.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border bg-[#f8fafc]">
                    <th
                      scope="col"
                      className="px-6 py-3 text-label-md text-muted-foreground"
                    >
                      Name
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-label-md text-muted-foreground"
                    >
                      Transport
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-label-md text-muted-foreground"
                    >
                      Connection
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-label-md text-muted-foreground"
                    >
                      Status
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-3 text-right text-label-md text-muted-foreground"
                    >
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {mcpServers.map((server) => (
                    <tr
                      key={server.id}
                      className="border-b border-border last:border-b-0 hover:bg-muted/40"
                    >
                      <td className="px-6 py-3">
                        <p className="font-medium text-foreground">{server.name}</p>
                        <code className="mt-1 block text-xs text-muted-foreground">
                          {server.id}
                        </code>
                      </td>
                      <td className="px-4 py-3 uppercase text-muted-foreground">
                        {server.transport}
                      </td>
                      <td className="px-4 py-3">
                        <code className="text-xs text-foreground">
                          {server.connectionSummary}
                        </code>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={server.enabled ? "success" : "muted"}>
                          {server.enabled ? "Enabled" : "Disabled"}
                        </Badge>
                      </td>
                      <td className="px-6 py-3 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeMcpServer(server.id)}
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

      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-6 py-5">
          <div>
            <h2 className="text-headline-md text-foreground">Registered tools</h2>
            <p className="mt-1 text-body-md text-muted-foreground">
              Tools the orchestrator and executor can discover.
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
                    <th
                      scope="col"
                      className="px-6 py-3 text-label-md text-muted-foreground"
                    >
                      Name
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-label-md text-muted-foreground"
                    >
                      Kind
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-label-md text-muted-foreground"
                    >
                      Description
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-label-md text-muted-foreground"
                    >
                      Config
                    </th>
                    <th
                      scope="col"
                      className="px-6 py-3 text-right text-label-md text-muted-foreground"
                    >
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
