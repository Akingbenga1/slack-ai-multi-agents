"use client";

import { FormEvent, useEffect, useState } from "react";
import { ApiError, apiClient } from "@/lib/api";
import panel from "@/components/dashboard/panel.module.css";
import styles from "@/components/tools/tools.module.css";

export type DiscoveredTool = {
  id: string;
  name: string;
  summary: string;
  source: string;
  kind?: "cli";
  config?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
};

type DiscoverySearchResponse = {
  kind: "cli";
  query: string;
  tools: DiscoveredTool[];
};

type Props = {
  accessToken?: string | null;
  onSelect?: (tool: DiscoveredTool) => void;
};

const CLI_DISCOVERY_PATH = "/discovery/cli-tools";

function cliCommandFromConfig(tool: DiscoveredTool): string | null {
  const config = tool.config;
  if (!config || typeof config !== "object") return null;
  const command = config.command;
  return typeof command === "string" && command.trim() ? command.trim() : null;
}

/** Subcommand descriptions only (purpose) — never usage / command examples. */
function cliSubcommandDescriptions(tool: DiscoveredTool): string[] {
  const config = tool.config;
  if (!config || typeof config !== "object") return [];
  const subcommands = config.subcommands;
  if (!subcommands || typeof subcommands !== "object" || Array.isArray(subcommands)) {
    return [];
  }
  const out: string[] = [];
  const seen = new Set<string>();
  for (const raw of Object.values(subcommands as Record<string, unknown>)) {
    let purpose = "";
    if (typeof raw === "string") {
      purpose = raw.trim();
    } else if (raw && typeof raw === "object") {
      const row = raw as Record<string, unknown>;
      purpose = String(
        row.purpose ?? row.description ?? row.summary ?? "",
      ).trim();
    }
    if (!purpose || seen.has(purpose)) continue;
    seen.add(purpose);
    out.push(purpose);
  }
  return out;
}

function metadataLine(tool: DiscoveredTool): string | null {
  const meta = tool.metadata;
  if (!meta) return null;
  const parts: string[] = [];
  if (typeof meta.platform === "string" && meta.platform) {
    parts.push(meta.platform);
  }
  if (typeof meta.score === "number" && Number.isFinite(meta.score)) {
    parts.push(`score ${meta.score.toFixed(1)}`);
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
      return "Sign in to search for tools.";
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

export function ToolDiscoveryPanel({ accessToken = null, onSelect }: Props) {
  const [token, setToken] = useState<string | null>(accessToken);
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [results, setResults] = useState<DiscoveredTool[]>([]);
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
      setError("Sign in to search for tools.");
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
        `${CLI_DISCOVERY_PATH}?${params.toString()}`,
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
    <section className={styles.workspaceCard} aria-labelledby="tool-discovery-cli">
      <div className={styles.cardHead}>
        <div>
          <h2 className={styles.cardTitle} id="tool-discovery-cli">
            CLI tool discovery
          </h2>
          <p className={styles.cardDesc}>
            Search the local tldr catalog via <code>/discovery/cli-tools</code> and pick a
            command to configure.
          </p>
        </div>
      </div>

      <form className={styles.discoveryForm} onSubmit={(ev) => void onDiscover(ev)}>
        <label className={panel.formLabel}>
          Search query
          <span className={panel.formHint}>Describe the capability you want to find</span>
          <div className={styles.discoverySearchRow}>
            <input
              value={query}
              onChange={(ev) => setQuery(ev.target.value)}
              placeholder="e.g. create png images, csv export, pdf convert"
              aria-label="CLI tool discovery query"
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
              <p className={panel.meta}>No CLI tools found for “{query.trim()}”.</p>
            </div>
          ) : null}
          {results.length > 0 ? (
            <>
              <p className={styles.discoveryResultCount} aria-live="polite">
                {results.length === 1 ? "1 CLI tool" : `${results.length} CLI tools`}
              </p>
              <ul className={styles.discoveryList}>
                {results.map((tool) => {
                  const extra = metadataLine(tool);
                  const command = cliCommandFromConfig(tool);
                  const subcommands = cliSubcommandDescriptions(tool);
                  return (
                    <li key={tool.id} className={styles.discoveryItem}>
                      <div>
                        <p className={styles.discoveryItemTitle}>{tool.name}</p>
                        <p className={styles.discoveryItemText}>
                          {tool.summary || "No description"}
                        </p>
                        {command ? (
                          <p className={styles.discoveryCommand}>
                            <code>{command}</code>
                          </p>
                        ) : null}
                        {subcommands.length > 0 ? (
                          <div className={styles.discoverySubcommands}>
                            <p className={styles.discoverySubcommandsLabel}>
                              Subcommands
                            </p>
                            <ul className={styles.discoverySubcommandsList}>
                              {subcommands.map((desc) => (
                                <li key={desc}>{desc}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        <p className={panel.meta}>
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
          <p className={panel.meta}>Searching CLI tools…</p>
        </div>
      ) : (
        <div className={styles.discoveryIdle}>
          <p className={panel.meta}>Enter a query to search available CLI tools.</p>
        </div>
      )}
    </section>
  );
}
