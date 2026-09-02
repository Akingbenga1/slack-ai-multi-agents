"use client";

import { FormEvent, useEffect, useState } from "react";
import { signIn } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, apiClient, getApiBaseUrl } from "@/lib/api";
import { AuthFormField, authInputClassName } from "@/components/auth/PublicAuthShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

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
    <p className="text-body-md text-muted-foreground">
      This page is for accepting invitations. If you arrived here without a link from your
      admin, ask them to resend it — or{" "}
      <Link href="/signup" className="font-medium text-primary hover:underline">
        create your own organisation
      </Link>{" "}
      instead.
    </p>
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
    <div className="space-y-6">
      <p className="text-body-md text-muted-foreground">
        Invite another <strong className="text-foreground">org admin</strong> to this organisation.
        Copy the invitation link and share it with them directly.
      </p>
      <form onSubmit={(ev) => void onSubmit(ev)} className="space-y-4">
        <AuthFormField label="Email">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="colleague@example.com"
            className={authInputClassName}
          />
        </AuthFormField>
        {error ? (
          <p className="text-sm text-danger" role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={pending} className="rounded-full">
          {pending ? "Creating…" : "Create invite link"}
        </Button>
      </form>
      {lastUrl ? (
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-headline-sm">Copy invitation link</CardTitle>
          </CardHeader>
          <CardContent>
            <code className="block break-all text-sm text-foreground">{lastUrl}</code>
          </CardContent>
        </Card>
      ) : null}
      {rows.length > 0 ? (
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-border pb-4">
            <div>
              <CardTitle className="text-headline-sm">Recent invites</CardTitle>
              <CardDescription>{rows.length} total</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="divide-y divide-border p-0">
            {rows.map((row) => (
              <div key={row.id} className="px-6 py-4">
                <p className="font-medium text-foreground">{row.email}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  <Badge variant={row.used_at ? "default" : "warning"} className="mr-2">
                    {row.used_at ? "used" : "pending"}
                  </Badge>
                  {row.expires_at ? `expires ${row.expires_at}` : ""}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
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
      <p className="text-body-md text-danger" role="alert">
        {loadError}
      </p>
    );
  }
  if (!preview) {
    return <p className="text-body-md text-muted-foreground">Loading invite…</p>;
  }

  return (
    <div className="space-y-4">
      <p className="text-body-md text-muted-foreground">
        Join <strong className="text-foreground">{preview.tenant_name || preview.tenant_slug}</strong> as{" "}
        {preview.role}. This does not create a new organisation.
      </p>
      <form onSubmit={(ev) => void onSubmit(ev)} className="space-y-4">
        <AuthFormField label="Email">
          <input
            type="email"
            value={preview.email}
            readOnly
            className={authInputClassName + " bg-muted"}
          />
        </AuthFormField>
        <AuthFormField label="Display name" hint="Optional">
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className={authInputClassName}
          />
        </AuthFormField>
        <AuthFormField label="Password" hint="Minimum 8 characters">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            className={authInputClassName}
          />
        </AuthFormField>
        {error ? (
          <p className="text-sm text-danger" role="alert">
            {error}
          </p>
        ) : null}
        <Button type="submit" disabled={pending} className="w-full rounded-full">
          {pending ? "Joining…" : "Accept invite"}
        </Button>
      </form>
    </div>
  );
}
