/** Remaining local fixtures for Create-tool HTTP preview only — not MCP install. */

export type MockMcpServer = {
  id: string;
  name: string;
  transport: "stdio" | "http";
  enabled: boolean;
  connectionSummary: string;
  createdAt: string;
};

export type MockToolKind = "mcp" | "cli" | "http" | "code";

export type MockTool = {
  id: string;
  name: string;
  kind: MockToolKind;
  description: string;
  mcpServerId: string | null;
  mcpServerName: string | null;
  configSummary: string;
  createdAt: string;
};

const DEMO_TENANT = "11111111-1111-1111-1111-111111111111";

export function createMockTool(input: {
  name: string;
  kind: MockToolKind;
  description: string;
  mcpServerId: string | null;
  mcpServers: MockMcpServer[];
  cliCommand?: string;
  httpUrl?: string;
}): MockTool {
  const server = input.mcpServers.find((s) => s.id === input.mcpServerId);
  let configSummary = "—";
  if (input.kind === "mcp") {
    configSummary = server ? `MCP tool on ${server.name}` : "MCP (no server selected)";
  } else if (input.kind === "cli") {
    configSummary = input.cliCommand?.trim() || "CLI command";
  } else if (input.kind === "http") {
    configSummary = input.httpUrl?.trim() || "HTTP endpoint";
  } else {
    configSummary = "Inline code handler";
  }

  return {
    id: `tool-${Date.now()}`,
    name: input.name.trim(),
    kind: input.kind,
    description: input.description.trim(),
    mcpServerId: input.mcpServerId,
    mcpServerName: server?.name ?? null,
    configSummary,
    createdAt: new Date().toISOString(),
  };
}

export function getMockTenantOptions(): Array<{
  id: string;
  name: string;
  slug: string;
}> {
  return [
    {
      id: DEMO_TENANT,
      name: "Demo Organisation",
      slug: "demo",
    },
    {
      id: "22222222-2222-2222-2222-222222222222",
      name: "Organisation 22222222",
      slug: "org-22222222",
    },
  ];
}
