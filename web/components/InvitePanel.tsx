"use client";

import { FormEvent, useEffect, useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, apiClient, getApiBaseUrl } from "@/lib/api";
import panel from "@/components/dashboard/panel.module.css";

type InviteRow = {
  id: string;
  email: string;
  role: string;
  expires_at: string | null;
  used_at: string | null;
  created_at: string | null;
  invite_url?: string;
  token?: string;
};

type Preview = {
  email: string;
  role: string;
  tenant_name: string | null;
  tenant_slug: string | null;
  expires_at: string;
};

function detailMessage(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

type Props = {
  accessToken: string | null;
  tenantId: string | null;
  inviteToken: string | null;
  isOrgAdmin: boolean;
};

export function InvitePanel({
  accessToken,
  tenantId,
  inviteToken,
  isOrgAdmin,
}: Props) {
  if (inviteToken) {
    return <AcceptInvite token={inviteToken} />;
  }
  if (isOrgAdmin && accessToken) {
    return <CreateInvite accessToken={accessToken} tenantId={tenantId} />;
  }
  return (
    <>
      <p>
        Org admins can invite additional admins to the <strong>same</strong>{" "}
        organisation. Invited users cannot create a second org from the link.
      </p>
      <p className={panel.meta}>
        There is no email send in this sprint — copy the magic-link URL
        (<code>WEB_APP_URL/invite?token=…</code>). Sign in to create an invite from{" "}
        <Link href="/app/invite">Invite team</Link>, or open a link you were given.
      </p>
      <p>
        <Link href="/login">Sign in</Link>
        {" · "}
        <Link href="/signup">Create organisation</Link>
      </p>
    </>
  );
}

function CreateInvite({
  accessToken,
  tenantId,
}: {
  accessToken: string;
  tenantId: string | null;
}) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [lastUrl, setLastUrl] = useState<string | null>(null);
  const [rows, setRows] = useState<InviteRow[]>([]);

  async function load() {
    try {
      const data = await apiClient.get<{ invites: InviteRow[] }>("/auth/invites", {
        accessToken,
        clientId: tenantId,
      });
      setRows(Array.isArray(data?.invites) ? data.invites : []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load invites");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, tenantId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setLastUrl(null);
    try {
      const data = await apiClient.post<InviteRow>("/auth/invites", {
        accessToken,
        clientId: tenantId,
        json: { email: email.trim().toLowerCase() },
      });
      if (data?.invite_url) {
        setLastUrl(data.invite_url);
      }
      setEmail("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create invite");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <p className={panel.sectionDesc}>
        Invite another <strong>org admin</strong> to this tenant. Copy the URL
        — SMTP is out of scope. They join this organisation only.
      </p>
      <form className={panel.formGrid} onSubmit={(ev) => void onSubmit(ev)}>
        <label className={panel.formLabel}>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="colleague@example.com"
          />
        </label>
        {error ? (
          <p className={panel.error} role="alert">
            {error}
          </p>
        ) : null}
        <div className={panel.formRow}>
          <button type="submit" className={panel.btnPrimary} disabled={pending}>
            {pending ? "Creating…" : "Create invite link"}
          </button>
        </div>
      </form>
      {lastUrl ? (
        <p className={panel.infoBanner} style={{ marginTop: "1rem" }}>
          Copy this URL now:
          <br />
          <code style={{ wordBreak: "break-all" }}>{lastUrl}</code>
        </p>
      ) : null}
      {rows.length > 0 ? (
        <div style={{ marginTop: "1.5rem" }}>
          <div className={panel.sectionHeader}>
            <h2 className={panel.sectionTitle}>Recent invites</h2>
            <span className={panel.sectionCount}>{rows.length}</span>
          </div>
          <ul className={panel.detailList}>
            {rows.map((row) => (
              <li key={row.id} className={panel.detailItem}>
                <p className={panel.detailLabel}>{row.email}</p>
                <p className={panel.detailValue}>
                  {row.used_at ? "used" : "pending"}
                  {row.expires_at ? ` · expires ${row.expires_at}` : ""}
                </p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}

function AcceptInvite({ token }: { token: string }) {
  const router = useRouter();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const base = getApiBaseUrl();
        const res = await fetch(
          `${base}/auth/invites/preview?token=${encodeURIComponent(token)}`,
        );
        const body = (await res.json().catch(() => null)) as unknown;
        if (!res.ok) {
          if (!cancelled) {
            setLoadError(detailMessage(body, "Invite is not valid"));
          }
          return;
        }
        if (!cancelled) setPreview(body as Preview);
      } catch {
        if (!cancelled) setLoadError("Could not reach the API");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!preview) return;
    setPending(true);
    setError(null);
    try {
      const base = getApiBaseUrl();
      const res = await fetch(`${base}/auth/invites/accept`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          password,
          display_name: displayName.trim() || undefined,
        }),
      });
      const body = (await res.json().catch(() => null)) as unknown;
      if (!res.ok) {
        setError(detailMessage(body, "Could not accept invite"));
        return;
      }
      const result = await signIn("credentials", {
        email: preview.email,
        password,
        redirect: false,
      });
      if (result?.error) {
        setError("Joined, but sign-in failed. Try /login.");
        return;
      }
      router.push("/app");
      router.refresh();
    } catch {
      setError("Could not reach the API");
    } finally {
      setPending(false);
    }
  }

  if (loadError) {
    return (
      <p style={{ color: "var(--error)" }} role="alert">
        {loadError}
      </p>
    );
  }
  if (!preview) {
    return <p>Loading invite…</p>;
  }

  return (
    <>
      <p>
        Join <strong>{preview.tenant_name || preview.tenant_slug}</strong> as{" "}
        {preview.role}. This does not create a new organisation.
      </p>
      <form
        onSubmit={(ev) => void onSubmit(ev)}
        style={{ display: "grid", gap: "0.75rem", maxWidth: 360 }}
      >
        <label style={{ display: "grid", gap: 4 }}>
          <span>Email</span>
          <input type="email" value={preview.email} readOnly style={{ padding: "0.5rem" }} />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Display name (optional)</span>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            style={{ padding: "0.5rem" }}
          />
        </label>
        <label style={{ display: "grid", gap: 4 }}>
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            style={{ padding: "0.5rem" }}
          />
        </label>
        {error ? (
          <p style={{ color: "var(--error)", margin: 0 }} role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" disabled={pending} style={{ padding: "0.6rem" }}>
          {pending ? "Joining…" : "Accept invite"}
        </button>
      </form>
    </>
  );
}
