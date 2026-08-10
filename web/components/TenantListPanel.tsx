"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { ApiError, apiClient } from "@/lib/api";
import { useAuthenticatedResource } from "@/lib/useAuthenticatedResource";

export type TenantSummary = {
  id: string;
  slug: string;
  name: string;
  status: string;
  plan_status: string;
  slack_connected: boolean;
  slack_team_name?: string | null;
  last_synced_at?: string | null;
  last_sync_failure_at?: string | null;
  sync_enabled?: boolean;
};

type Props = {
  accessToken: string | null;
};

export function TenantListPanel({ accessToken }: Props) {
  const [creating, setCreating] = useState(false);
  const [createMsg, setCreateMsg] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [activatePlan, setActivatePlan] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: tenants,
    error: loadError,
    busy: loading,
    reload: load,
  } = useAuthenticatedResource(
    accessToken,
    async (token) => {
      const data = await apiClient.get<{ tenants: TenantSummary[] }>(
        "/admin/tenants",
        { accessToken: token, clientId: null },
      );
      return Array.isArray(data?.tenants) ? data.tenants : [];
    },
  );

  const error = actionError || loadError;
  const tenantList = tenants || [];

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) {
      setActionError("Not signed in");
      return;
    }
    setCreating(true);
    setCreateMsg(null);
    setActionError(null);
    try {
      const body: Record<string, unknown> = {
        name: name.trim(),
        slug: slug.trim().toLowerCase(),
        admin_email: adminEmail.trim().toLowerCase(),
        activate_plan: activatePlan,
      };
      if (adminPassword.trim()) {
        body.admin_password = adminPassword.trim();
      }
      const data = await apiClient.post<{
        tenant?: { id?: string; slug?: string };
        admin_password?: string;
      }>("/admin/tenants", {
        accessToken,
        clientId: null,
        json: body,
      });
      const tid = data?.tenant?.id;
      const pwd = data?.admin_password;
      setCreateMsg(
        pwd
          ? `Created ${data?.tenant?.slug}. Generated password: ${pwd} (save now).`
          : `Created ${data?.tenant?.slug}${tid ? ` (${tid})` : ""}.`,
      );
      setName("");
      setSlug("");
      setAdminEmail("");
      setAdminPassword("");
      setActivatePlan(false);
      await load();
    } catch (err) {
      setActionError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Create failed",
      );
    } finally {
      setCreating(false);
    }
  }

  return (
    <section>
      <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
        <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Tenants</h2>
        <button type="button" onClick={() => void load()} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      <form
        onSubmit={(ev) => void onCreate(ev)}
        style={{
          marginTop: "1.25rem",
          padding: "1rem 0",
          borderTop: "1px solid #eee",
          borderBottom: "1px solid #eee",
          display: "grid",
          gap: "0.6rem",
          maxWidth: 480,
        }}
      >
        <h3 style={{ margin: 0, fontSize: "1rem" }}>Create organisation</h3>
        <p style={{ margin: 0, color: "#555", fontSize: "0.9rem" }}>
          Second-org stand-up (PO-04). Slack install + knowledge stay per tenant.
        </p>
        <label style={{ display: "grid", gap: "0.25rem" }}>
          Name
          <input
            value={name}
            onChange={(ev) => setName(ev.target.value)}
            required
            autoComplete="off"
          />
        </label>
        <label style={{ display: "grid", gap: "0.25rem" }}>
          Slug
          <input
            value={slug}
            onChange={(ev) => setSlug(ev.target.value)}
            required
            pattern="[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?"
            placeholder="acme-co"
            autoComplete="off"
          />
        </label>
        <label style={{ display: "grid", gap: "0.25rem" }}>
          Org admin email
          <input
            type="email"
            value={adminEmail}
            onChange={(ev) => setAdminEmail(ev.target.value)}
            required
            autoComplete="off"
          />
        </label>
        <label style={{ display: "grid", gap: "0.25rem" }}>
          Org admin password (optional — generated if blank)
          <input
            type="password"
            value={adminPassword}
            onChange={(ev) => setAdminPassword(ev.target.value)}
            minLength={8}
            autoComplete="new-password"
          />
        </label>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <input
            type="checkbox"
            checked={activatePlan}
            onChange={(ev) => setActivatePlan(ev.target.checked)}
          />
          Activate plan locally (demo; skip Stripe)
        </label>
        <button type="submit" disabled={creating || !accessToken}>
          {creating ? "Creating…" : "Create organisation"}
        </button>
        {createMsg ? (
          <p style={{ color: "#0a7a32", margin: 0 }} role="status">
            {createMsg}
          </p>
        ) : null}
      </form>

      {error ? (
        <p style={{ color: "#b00020" }} role="alert">
          {error}
        </p>
      ) : null}
      {!error && tenantList.length === 0 && !loading && tenants !== undefined ? (
        <p>No tenants yet.</p>
      ) : null}
      {tenantList.length > 0 ? (
        <table
          style={{
            width: "100%",
            marginTop: "1rem",
            borderCollapse: "collapse",
            fontSize: "0.95rem",
          }}
        >
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid #ddd" }}>
              <th style={{ padding: "0.4rem" }}>Name</th>
              <th style={{ padding: "0.4rem" }}>Status</th>
              <th style={{ padding: "0.4rem" }}>Plan</th>
              <th style={{ padding: "0.4rem" }}>Slack</th>
              <th style={{ padding: "0.4rem" }}>Last sync</th>
            </tr>
          </thead>
          <tbody>
            {tenantList.map((t) => (
              <tr key={t.id} style={{ borderBottom: "1px solid #eee" }}>
                <td style={{ padding: "0.45rem" }}>
                  <Link href={`/admin/tenants/${t.id}`}>
                    {t.name}
                  </Link>
                  <div style={{ color: "#666", fontSize: "0.85rem" }}>
                    {t.slug}
                  </div>
                </td>
                <td style={{ padding: "0.45rem" }}>{t.status}</td>
                <td style={{ padding: "0.45rem" }}>{t.plan_status}</td>
                <td style={{ padding: "0.45rem" }}>
                  {t.slack_connected
                    ? t.slack_team_name || "connected"
                    : "—"}
                </td>
                <td style={{ padding: "0.45rem", fontSize: "0.85rem" }}>
                  {t.last_synced_at || "—"}
                  {t.last_sync_failure_at ? (
                    <div style={{ color: "#b00020" }}>sync failure recorded</div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
