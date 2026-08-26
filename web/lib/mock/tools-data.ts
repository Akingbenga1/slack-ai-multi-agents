/** Static mock fixtures for tool / MCP UI previews — not wired to the API. */

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

const SEED_MCP: MockMcpServer[] = [
  {
    id: "mcp-seed-bundled",
    name: "bundled",
    transport: "stdio",
    enabled: true,
    connectionSummary: "python -m mcp_server",
    createdAt: "2026-06-01T10:00:00Z",
  },
];

const SEED_TOOLS: MockTool[] = [
  {
    id: "tool-seed-search",
    name: "search_knowledge",
    kind: "mcp",
    description: "Semantic search over tenant knowledge base",
    mcpServerId: "mcp-seed-bundled",
    mcpServerName: "bundled",
    configSummary: "MCP tool on bundled server",
    createdAt: "2026-06-01T10:05:00Z",
  },
  {
    id: "tool-seed-draft",
    name: "draft_report",
    kind: "mcp",
    description: "Generate structured report drafts",
    mcpServerId: "mcp-seed-bundled",
    mcpServerName: "bundled",
    configSummary: "MCP tool on bundled server",
    createdAt: "2026-06-01T10:06:00Z",
  },
];

export function getMockMcpServers(_tenantId?: string): MockMcpServer[] {
  return SEED_MCP.map((row) => ({ ...row }));
}

export function getMockTools(_tenantId?: string): MockTool[] {
  return SEED_TOOLS.map((row) => ({ ...row }));
}

export function createMockMcpServer(input: {
  name: string;
  transport: "stdio" | "http";
  command?: string;
  url?: string;
  enabled: boolean;
}): MockMcpServer {
  const summary =
    input.transport === "stdio"
      ? input.command?.trim() || "stdio process"
      : input.url?.trim() || "http endpoint";
  return {
    id: `mcp-${Date.now()}`,
    name: input.name.trim(),
    transport: input.transport,
    enabled: input.enabled,
    connectionSummary: summary,
    createdAt: new Date().toISOString(),
  };
}

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

export function getMockPlatformToolsOverview(): Array<{
  tenantId: string;
  tenantName: string;
  tenantSlug: string;
  toolCount: number;
  mcpServerCount: number;
}> {
  return [
    {
      tenantId: DEMO_TENANT,
      tenantName: "Demo Organisation",
      tenantSlug: "demo",
      toolCount: SEED_TOOLS.length,
      mcpServerCount: SEED_MCP.length,
    },
    {
      tenantId: "22222222-2222-2222-2222-222222222222",
      tenantName: "Organisation 22222222",
      tenantSlug: "org-22222222",
      toolCount: 0,
      mcpServerCount: 0,
    },
  ];
}

export function getMockTenantOptions(): Array<{
  id: string;
  name: string;
  slug: string;
}> {
  return getMockPlatformToolsOverview().map((row) => ({
    id: row.tenantId,
    name: row.tenantName,
    slug: row.tenantSlug,
  }));
}

export function formatToolKind(kind: MockToolKind): string {
  return kind.toUpperCase();
}
