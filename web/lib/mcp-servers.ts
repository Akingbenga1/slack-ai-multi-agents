/** Tenant org-rep MCP server install client (`/mcp-servers`). */

import { ApiError, apiClient } from "@/lib/api";

export type McpReadiness = {
  ready?: boolean | null;
  endpoint?: string | null;
  tool_count?: number | null;
  tool_names?: string[] | null;
  error?: string | null;
  detail?: string | null;
};

export type McpServerRecord = {
  id: string;
  name: string;
  transport: string;
  url: string | null;
  enabled: boolean;
  has_service_credential: boolean;
  has_oauth_credential?: boolean;
  created_at: string | null;
  readiness?: McpReadiness | null;
};

export type McpServerListResponse = {
  servers: McpServerRecord[];
  count: number;
};

export type McpServerCreateInput = {
  name: string;
  url: string;
  service_token?: string | null;
  enabled?: boolean;
  verify?: boolean;
};

export type McpServerUpdateInput = {
  name?: string;
  url?: string;
  service_token?: string | null;
  clear_service_token?: boolean;
  enabled?: boolean;
  verify?: boolean;
};

export function mcpApiErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "Sign in to manage MCP servers.";
    if (err.status === 403) return err.message || "Not allowed.";
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

export async function listMcpServers(
  accessToken: string,
  tenantId: string | null,
): Promise<McpServerRecord[]> {
  const res = await apiClient.get<McpServerListResponse>("/mcp-servers", {
    accessToken,
    clientId: tenantId,
  });
  return res?.servers ?? [];
}

export async function createMcpServer(
  accessToken: string,
  tenantId: string | null,
  input: McpServerCreateInput,
): Promise<McpServerRecord> {
  const body: Record<string, unknown> = {
    name: input.name.trim(),
    url: input.url.trim(),
    enabled: input.enabled ?? true,
    verify: input.verify ?? true,
  };
  const token = (input.service_token || "").trim();
  if (token) body.service_token = token;
  const res = await apiClient.post<McpServerRecord>("/mcp-servers", {
    accessToken,
    clientId: tenantId,
    json: body,
  });
  if (!res) throw new Error("Empty MCP server create response");
  return res;
}

export async function updateMcpServer(
  accessToken: string,
  tenantId: string | null,
  serverId: string,
  input: McpServerUpdateInput,
): Promise<McpServerRecord> {
  const body: Record<string, unknown> = {};
  if (input.name !== undefined) body.name = input.name.trim();
  if (input.url !== undefined) body.url = input.url.trim();
  if (input.enabled !== undefined) body.enabled = input.enabled;
  if (input.verify !== undefined) body.verify = input.verify;
  if (input.clear_service_token) body.clear_service_token = true;
  if (input.service_token !== undefined && input.service_token !== null) {
    const token = input.service_token.trim();
    if (token) body.service_token = token;
  }
  const res = await apiClient.patch<McpServerRecord>(
    `/mcp-servers/${encodeURIComponent(serverId)}`,
    { accessToken, clientId: tenantId, json: body },
  );
  if (!res) throw new Error("Empty MCP server update response");
  return res;
}

export async function deleteMcpServer(
  accessToken: string,
  tenantId: string | null,
  serverId: string,
): Promise<void> {
  await apiClient.delete(`/mcp-servers/${encodeURIComponent(serverId)}`, {
    accessToken,
    clientId: tenantId,
  });
}

export async function checkMcpServer(
  accessToken: string,
  tenantId: string | null,
  serverId: string,
): Promise<McpServerRecord> {
  const res = await apiClient.post<McpServerRecord>(
    `/mcp-servers/${encodeURIComponent(serverId)}/check`,
    { accessToken, clientId: tenantId },
  );
  if (!res) throw new Error("Empty MCP server check response");
  return res;
}

export type McpOAuthStartResponse = {
  server_id: string;
  authorization_url: string;
  state: string;
};

export async function startMcpOAuth(
  accessToken: string,
  tenantId: string | null,
  serverId: string,
): Promise<McpOAuthStartResponse> {
  const res = await apiClient.post<McpOAuthStartResponse>(
    `/mcp-servers/${encodeURIComponent(serverId)}/oauth/start`,
    { accessToken, clientId: tenantId },
  );
  if (!res) throw new Error("Empty MCP OAuth start response");
  return res;
}

export function readinessLabel(server: McpServerRecord): string {
  const r = server.readiness;
  if (!r) return "Not checked";
  if (r.ready === true) {
    const n = r.tool_count;
    return typeof n === "number" ? `Ready · ${n} tool(s)` : "Ready";
  }
  if (r.error) return r.error;
  if (r.detail) return r.detail;
  return "Not ready";
}
