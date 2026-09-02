"use client";

import { FormEvent, useEffect, useState } from "react";
import { Search } from "lucide-react";
import { ApiError, apiClient } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export type DiscoveredMcpTool = {
  id: string;
  name: string;
  summary: string;
  source: string;
  kind?: "mcp";
  config?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
};

type DiscoverySearchResponse = {
  kind: "mcp";
  query: string;
  tools: DiscoveredMcpTool[];
};

type Props = {
  accessToken?: string | null;
  onSelect?: (tool: DiscoveredMcpTool) => void;
};

const MCP_DISCOVERY_PATH = "/discovery/mcp-tools";

const inputClassName =
  "min-w-0 flex-1 rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

function metadataLine(tool: DiscoveredMcpTool): string | null {
  const meta = tool.metadata;
  if (!meta) return null;
  const parts: string[] = [];
  if (typeof meta.transport === "string" && meta.transport) {
    parts.push(meta.transport);
  }
  if (typeof meta.version === "string" && meta.version) {
    parts.push(`v${meta.version}`);
  }
  if (typeof meta.status === "string" && meta.status) {
    parts.push(meta.status);
  }
  if (meta.official === true) {
    parts.push("official");
  }
  return parts.length ? parts.join(" · ") : null;
}

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body;
    if (typeof body === "object" && body !== null && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (
        typeof detail === "object" &&
        detail !== null &&
        "message" in detail &&
        typeof (detail as { message: unknown }).message === "string"
      ) {
        return (detail as { message: string }).message;
      }
    }
    if (err.status === 401) {
      return "Sign in to search for MCP servers.";
    }
    if (err.status === 404) {
      return "Discovery API is unavailable on this server. Restart the API with current routes.";
    }
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}

async function resolveSessionAccessToken(): Promise<string | null> {
  try {
    const res = await fetch("/api/auth/session", { credentials: "same-origin" });
    if (!res.ok) return null;
    const data = (await res.json()) as { accessToken?: string | null };
    return typeof data.accessToken === "string" && data.accessToken
      ? data.accessToken
      : null;
  } catch {
    return null;
  }
}

export function McpToolDiscoveryPanel({ accessToken = null, onSelect }: Props) {
  const [token, setToken] = useState<string | null>(accessToken);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [results, setResults] = useState<DiscoveredMcpTool[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (accessToken) {
      setToken(accessToken);
      return;
    }
    let cancelled = false;
    void resolveSessionAccessToken().then((next) => {
      if (!cancelled) setToken(next);
    });
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  async function onDiscover(ev: FormEvent) {
    ev.preventDefault();
    const q = query.trim();
    if (!q) return;

    const bearer = token ?? (await resolveSessionAccessToken());
    if (!bearer) {
      setSearched(true);
      setResults([]);
      setError("Sign in to search for MCP servers.");
      return;
    }
    if (bearer !== token) {
      setToken(bearer);
    }

    setSearching(true);
    setSearched(true);
    setError(null);
    setResults([]);
    try {
      const params = new URLSearchParams({ query: q });
      const body = await apiClient.get<DiscoverySearchResponse>(
        `${MCP_DISCOVERY_PATH}?${params.toString()}`,
        { accessToken: bearer, clientId: null },
      );
      setResults(body?.tools ?? []);
    } catch (err) {
      setResults([]);
      setError(errorMessage(err));
    } finally {
      setSearching(false);
    }
  }

  return (
    <Card aria-labelledby="tool-discovery-mcp">
      <CardHeader className="border-b border-border">
        <CardTitle id="tool-discovery-mcp" className="text-headline-md">
          MCP server discovery
        </CardTitle>
        <CardDescription>
          Search the Official MCP Registry via{" "}
          <code className="rounded bg-muted px-1 py-0.5 text-xs">
            /discovery/mcp-tools
          </code>{" "}
          and pick a server to configure.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-6">
        <form onSubmit={(ev) => void onDiscover(ev)}>
          <label className="block">
            <span className="text-sm font-medium text-foreground">Search query</span>
            <span className="mt-1 block text-sm text-muted-foreground">
              Describe the MCP capability or server you want
            </span>
            <div className="mt-2 flex flex-wrap gap-2">
              <input
                value={query}
                onChange={(ev) => setQuery(ev.target.value)}
                placeholder="e.g. postgres, slack, filesystem, github"
                aria-label="MCP server discovery query"
                maxLength={512}
                className={inputClassName}
              />
              <Button
                type="submit"
                className="rounded-full"
                disabled={searching || !query.trim()}
              >
                <Search className="h-4 w-4" />
                {searching ? "Searching…" : "Discover"}
              </Button>
            </div>
          </label>
        </form>

        {error ? (
          <p className="text-sm text-danger" role="alert">
            {error}
          </p>
        ) : null}

        {searched && !searching ? (
          <div className="space-y-3">
            {!error && results.length === 0 ? (
              <div className="rounded-lg border border-border bg-[#f8fafc] px-4 py-6 text-center">
                <p className="font-medium text-foreground">No matches</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  No MCP servers found for “{query.trim()}”.
                </p>
              </div>
            ) : null}
            {results.length > 0 ? (
              <>
                <p className="text-sm text-muted-foreground" aria-live="polite">
                  {results.length === 1
                    ? "1 MCP server"
                    : `${results.length} MCP servers`}
                </p>
                <ul className="space-y-3">
                  {results.map((tool) => {
                    const extra = metadataLine(tool);
                    return (
                      <li
                        key={tool.id}
                        className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-border p-4 hover:bg-muted/30"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-foreground">{tool.name}</p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {tool.summary || "No description"}
                          </p>
                          <p className="mt-2 text-xs text-muted-foreground">
                            {tool.id !== tool.name ? `${tool.id} · ` : ""}
                            {tool.source}
                            {extra ? ` · ${extra}` : ""}
                          </p>
                        </div>
                        {onSelect ? (
                          <Button
                            type="button"
                            size="sm"
                            className="shrink-0 rounded-full"
                            onClick={() => onSelect(tool)}
                          >
                            Use
                          </Button>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </>
            ) : null}
          </div>
        ) : searching ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }, (_, key) => (
              <div key={key} className="h-16 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Enter a query to search available MCP servers.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
