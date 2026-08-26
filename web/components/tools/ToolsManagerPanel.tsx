"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import panel from "@/components/dashboard/panel.module.css";
import styles from "@/components/tools/tools.module.css";
import {
  createMockMcpServer,
  formatToolKind,
  getMockMcpServers,
  getMockTools,
  type MockMcpServer,
  type MockTool,
  type MockToolKind,
} from "@/lib/mock/tools-data";

type Props = {
  tenantLabel?: string;
  createHref: string;
};

function kindBadgeClass(kind: MockToolKind): string {
  if (kind === "mcp") return styles.kindMcp;
  if (kind === "cli") return styles.kindCli;
  if (kind === "http") return styles.kindHttp;
  return styles.kindCode;
}

export function ToolsManagerPanel({ tenantLabel, createHref }: Props) {
  const [tools, setTools] = useState<MockTool[]>(() => getMockTools());
  const [mcpServers, setMcpServers] = useState<MockMcpServer[]>(() => getMockMcpServers());
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
    <section>
      {tenantLabel ? (
        <p className={panel.meta} style={{ marginBottom: "1rem" }}>
          Managing tools for <strong>{tenantLabel}</strong>.
        </p>
      ) : null}

      <div className={panel.toolbar}>
        <div className={panel.toolbarLeft}>
          <Link href={createHref}>
            <button type="button">New tool</button>
          </Link>
          <button type="button" onClick={() => setShowMcpForm(true)}>
            Add MCP server
          </button>
        </div>
        <p className={panel.meta}>
          {tools.length} tool(s) · {mcpServers.length} MCP server(s)
        </p>
      </div>

      {message ? (
        <p className={panel.infoBanner} role="status">
          {message}
        </p>
      ) : null}

      {showMcpForm ? (
        <form className={styles.formPanel} onSubmit={(ev) => void onAddMcpServer(ev)}>
          <h3 className={styles.formPanelTitle}>New MCP server</h3>
          <div className={panel.formGrid}>
            <label className={panel.formLabel}>
              Server name
              <span className={panel.formHint}>Unique per tenant — e.g. bundled, github, custom</span>
              <input value={mcpName} onChange={(ev) => setMcpName(ev.target.value)} required />
            </label>
            <label className={panel.formLabel}>
              Transport
              <select
                value={mcpTransport}
                onChange={(ev) => setMcpTransport(ev.target.value as "stdio" | "http")}
              >
                <option value="stdio">stdio (local process)</option>
                <option value="http">http (remote server)</option>
              </select>
            </label>
            {mcpTransport === "stdio" ? (
              <label className={panel.formLabel}>
                Launch command
                <input
                  value={mcpCommand}
                  onChange={(ev) => setMcpCommand(ev.target.value)}
                  placeholder="python -m mcp_server"
                  required
                />
              </label>
            ) : (
              <label className={panel.formLabel}>
                Server URL
                <input
                  type="url"
                  value={mcpUrl}
                  onChange={(ev) => setMcpUrl(ev.target.value)}
                  placeholder="https://mcp.example.com/sse"
                  required
                />
              </label>
            )}
            <label className={panel.checkboxRow}>
              <input
                type="checkbox"
                checked={mcpEnabled}
                onChange={(ev) => setMcpEnabled(ev.target.checked)}
              />
              Enabled — agent can discover tools from this server
            </label>
            <div className={panel.formRow}>
              <button type="submit">Save MCP server</button>
              <button type="button" onClick={resetMcpForm}>
                Cancel
              </button>
            </div>
          </div>
        </form>
      ) : null}

      <section className={panel.section}>
        <div className={panel.sectionHeader}>
          <h2 className={panel.sectionTitle}>MCP servers</h2>
          <span className={panel.sectionCount}>{mcpServers.length}</span>
        </div>
        <p className={panel.sectionDesc}>
          Connected MCP processes or HTTP endpoints. Register a server before adding MCP-kind tools.
        </p>
        {mcpServers.length > 0 ? (
          <div className={panel.tableWrap}>
            <table className={panel.table}>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Transport</th>
                  <th scope="col">Connection</th>
                  <th scope="col">Status</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {mcpServers.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <span className={panel.tableLink}>{s.name}</span>
                      <div className={panel.tableMuted}>
                        <code>{s.id}</code>
                      </div>
                    </td>
                    <td>{s.transport}</td>
                    <td className={panel.tableMuted}>
                      <code>{s.connectionSummary}</code>
                    </td>
                    <td>
                      <span
                        className={`${panel.badge} ${s.enabled ? panel.badgeOk : panel.badgeNeutral}`}
                      >
                        {s.enabled ? "enabled" : "disabled"}
                      </span>
                    </td>
                    <td>
                      <button
                        type="button"
                        className={`${panel.btnSm} ${panel.btnDanger}`}
                        onClick={() => removeMcpServer(s.id)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className={panel.empty}>No MCP servers yet — add one to expose MCP tools.</p>
        )}
      </section>

      <section className={panel.section}>
        <div className={panel.sectionHeader}>
          <h2 className={panel.sectionTitle}>Registered tools</h2>
          <span className={panel.sectionCount}>{tools.length}</span>
        </div>
        <p className={panel.sectionDesc}>
          Tools the orchestrator and executor can discover. Create CLI, MCP, or HTTP tools on the New
          tool page.
        </p>
        {tools.length > 0 ? (
          <div className={panel.tableWrap}>
            <table className={panel.table}>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Kind</th>
                  <th scope="col">Description</th>
                  <th scope="col">Config</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {tools.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <span className={panel.tableLink}>{t.name}</span>
                      {t.mcpServerName ? (
                        <div className={panel.tableMuted}>via {t.mcpServerName}</div>
                      ) : null}
                    </td>
                    <td>
                      <span className={`${panel.badge} ${kindBadgeClass(t.kind)}`}>
                        {formatToolKind(t.kind)}
                      </span>
                    </td>
                    <td className={panel.tableMuted}>{t.description || "—"}</td>
                    <td className={panel.tableMuted}>{t.configSummary}</td>
                    <td>
                      <button
                        type="button"
                        className={`${panel.btnSm} ${panel.btnDanger}`}
                        onClick={() => removeTool(t.name)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className={panel.empty}>
            <p style={{ margin: "0 0 0.75rem" }}>No tools registered yet.</p>
            <Link href={createHref}>
              <button type="button">Create first tool</button>
            </Link>
          </div>
        )}
      </section>
    </section>
  );
}
