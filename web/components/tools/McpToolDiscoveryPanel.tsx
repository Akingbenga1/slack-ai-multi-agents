"use client";

import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiClient } from "@/lib/api";
import panel from "@/components/dashboard/panel.module.css";
import styles from "@/components/tools/tools.module.css";

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
    <section className={styles.workspaceCard} aria-labelledby="tool-discovery-mcp">
      <div className={styles.cardHead}>
        <div>
          <h2 className={styles.cardTitle} id="tool-discovery-mcp">
            MCP server discovery
          </h2>
          <p className={styles.cardDesc}>
            Search the Official MCP Registry via <code>/discovery/mcp-tools</code> and pick a
            server to configure.
          </p>
        </div>
      </div>

      <form className={styles.discoveryForm} onSubmit={(ev) => void onDiscover(ev)}>
        <label className={panel.formLabel}>
          Search query
          <span className={panel.formHint}>Describe the MCP capability or server you want</span>
          <div className={styles.discoverySearchRow}>
            <input
              value={query}
              onChange={(ev) => setQuery(ev.target.value)}
              placeholder="e.g. postgres, slack, filesystem, github"
              aria-label="MCP server discovery query"
              maxLength={512}
            />
            <button
              type="submit"
              className={panel.btnPrimary}
              disabled={searching || !query.trim()}
            >
              {searching ? "Searching…" : "Discover"}
            </button>
          </div>
        </label>
      </form>

      {error ? (
        <p className={panel.error} role="alert">
          {error}
        </p>
      ) : null}

      {searched && !searching ? (
        <div className={styles.discoveryResults}>
          {!error && results.length === 0 ? (
            <div className={styles.discoveryEmpty}>
              <p className={styles.discoveryEmptyTitle}>No matches</p>
              <p className={panel.meta}>No MCP servers found for “{query.trim()}”.</p>
            </div>
          ) : null}
          {results.length > 0 ? (
            <>
              <p className={styles.discoveryResultCount} aria-live="polite">
                {results.length === 1
                  ? "1 MCP server"
                  : `${results.length} MCP servers`}
              </p>
              <ul className={styles.discoveryList}>
                {results.map((tool) => {
                  const extra = metadataLine(tool);
                  return (
                    <li key={tool.id} className={styles.discoveryItem}>
                      <div>
                        <p className={styles.discoveryItemTitle}>{tool.name}</p>
                        <p className={styles.discoveryItemText}>
                          {tool.summary || "No description"}
                        </p>
                        <p className={panel.meta}>
                          {tool.id !== tool.name ? `${tool.id} · ` : ""}
                          {tool.source}
                          {extra ? ` · ${extra}` : ""}
                        </p>
                      </div>
                      {onSelect ? (
                        <button type="button" onClick={() => onSelect(tool)}>
                          Use
                        </button>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </>
          ) : null}
        </div>
      ) : searching ? (
        <div className={styles.discoveryIdle}>
          <p className={panel.meta}>Searching MCP registry…</p>
        </div>
      ) : (
        <div className={styles.discoveryIdle}>
          <p className={panel.meta}>Enter a query to search available MCP servers.</p>
        </div>
      )}
    </section>
  );
}
