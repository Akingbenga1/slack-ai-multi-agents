"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import panel from "@/components/dashboard/panel.module.css";
import { ApiError, apiClient } from "@/lib/api";
import { slugFromName } from "@/lib/slug";

type Props = {
  accessToken: string | null;
};

export function TenantCreateForm({ accessToken }: Props) {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatedPassword, setGeneratedPassword] = useState<string | null>(null);
  const [createdTenantId, setCreatedTenantId] = useState<string | null>(null);
  const [pendingRedirect, setPendingRedirect] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugManual, setSlugManual] = useState(false);
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [adminDisplayName, setAdminDisplayName] = useState("");
  const [activatePlan, setActivatePlan] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!accessToken) {
      setError("Not signed in");
      return;
    }
    setCreating(true);
    setError(null);
    setGeneratedPassword(null);
    setCreatedTenantId(null);
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
      if (adminDisplayName.trim()) {
        body.admin_display_name = adminDisplayName.trim();
      }
      const data = await apiClient.post<{
        tenant?: { id?: string; slug?: string };
        admin_password?: string;
      }>("/admin/tenants", {
        accessToken,
        clientId: null,
        json: body,
      });
      const tenantId = data?.tenant?.id;
      if (data?.admin_password) {
        setGeneratedPassword(data.admin_password);
      }
      if (tenantId) {
        setCreatedTenantId(tenantId);
        if (!data?.admin_password) {
          setPendingRedirect(true);
        }
      }
    } catch (err) {
      setError(
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

  useEffect(() => {
    if (pendingRedirect && createdTenantId) {
      router.push(`/admin/tenants/${createdTenantId}`);
    }
  }, [pendingRedirect, createdTenantId, router]);

  if (pendingRedirect && createdTenantId) {
    return (
      <p className={panel.infoBanner} role="status">
        Organisation created — opening tenant detail…
      </p>
    );
  }

  return (
    <section className={panel.section}>
      <div className={panel.sectionHeader}>
        <h2 className={panel.sectionTitle}>Organisation details</h2>
      </div>
      <p className={panel.sectionDesc}>
        Creates tenant row, org admin membership, billing customer, and default agent config
        (PO-04). Slug is auto-filled from the name but can be edited — it is permanent once
        created.
      </p>

      {error ? (
        <p className={panel.error} role="alert">
          {error}
        </p>
      ) : null}

      {generatedPassword && createdTenantId ? (
        <div className={panel.warnBanner} role="status">
          <p style={{ margin: "0 0 0.5rem", fontWeight: 600 }}>Organisation created</p>
          <p style={{ margin: "0 0 0.5rem", color: "var(--muted)" }}>
            Save the generated org admin password now — it will not be shown again.
          </p>
          <p style={{ margin: "0 0 0.75rem" }}>
            <code>{generatedPassword}</code>
          </p>
          <div className={panel.formRow}>
            <Link href={`/admin/tenants/${createdTenantId}`}>
              <button type="button">Open tenant detail</button>
            </Link>
            <Link href="/admin/tenants">
              <button type="button">Back to list</button>
            </Link>
          </div>
        </div>
      ) : (
        <form className={panel.formGrid} onSubmit={(ev) => void onSubmit(ev)}>
          <label className={panel.formLabel}>
            Organisation name
            <input
              value={name}
              onChange={(ev) => {
                const next = ev.target.value;
                setName(next);
                if (!slugManual) {
                  setSlug(slugFromName(next));
                }
              }}
              required
              maxLength={255}
              autoComplete="organization"
            />
          </label>
          <label className={panel.formLabel}>
            Slug
            <span className={panel.formHint}>
              Auto-generated from name — edit to override. Cannot be changed later via API.
            </span>
            <input
              value={slug}
              onChange={(ev) => {
                setSlugManual(true);
                setSlug(ev.target.value.toLowerCase());
              }}
              required
              pattern="[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?"
              placeholder="acme-co"
              autoComplete="off"
            />
          </label>
          <label className={panel.formLabel}>
            Org admin email
            <input
              type="email"
              value={adminEmail}
              onChange={(ev) => setAdminEmail(ev.target.value)}
              required
              autoComplete="off"
            />
          </label>
          <label className={panel.formLabel}>
            Org admin display name
            <span className={panel.formHint}>Optional</span>
            <input
              value={adminDisplayName}
              onChange={(ev) => setAdminDisplayName(ev.target.value)}
              maxLength={255}
              autoComplete="name"
            />
          </label>
          <label className={panel.formLabel}>
            Org admin password
            <span className={panel.formHint}>Optional — generated if blank (min 8 chars if set)</span>
            <input
              type="password"
              value={adminPassword}
              onChange={(ev) => setAdminPassword(ev.target.value)}
              minLength={8}
              autoComplete="new-password"
            />
          </label>
          <label className={panel.checkboxRow}>
            <input
              type="checkbox"
              checked={activatePlan}
              onChange={(ev) => setActivatePlan(ev.target.checked)}
            />
            Activate plan locally (demo; skip Stripe Checkout)
          </label>
          <div className={panel.formRow}>
            <button type="submit" disabled={creating || !accessToken}>
              {creating ? "Creating…" : "Create organisation"}
            </button>
            <Link href="/admin/tenants">
              <button type="button">Cancel</button>
            </Link>
          </div>
        </form>
      )}
    </section>
  );
}
