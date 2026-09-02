"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ApiError, apiClient } from "@/lib/api";
import { AuthFormField, authInputClassName } from "@/components/auth/PublicAuthShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type MemberRow = {
  user_id: string;
  email: string;
  display_name: string | null;
  role: string;
  joined_at: string | null;
  is_active: boolean;
};

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

type Props = {
  accessToken: string;
  tenantId: string | null;
  currentUserId: string | null;
};

export function TeamPanel({ accessToken, tenantId, currentUserId }: Props) {
  const [members, setMembers] = useState<MemberRow[]>([]);
  const [invites, setInvites] = useState<InviteRow[]>([]);
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [lastUrl, setLastUrl] = useState<string | null>(null);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [busyInviteId, setBusyInviteId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [membersData, invitesData] = await Promise.all([
        apiClient.get<{ members: MemberRow[] }>("/auth/members", {
          accessToken,
          clientId: tenantId,
        }),
        apiClient.get<{ invites: InviteRow[] }>("/auth/invites", {
          accessToken,
          clientId: tenantId,
        }),
      ]);
      setMembers(Array.isArray(membersData?.members) ? membersData.members : []);
      setInvites(Array.isArray(invitesData?.invites) ? invitesData.invites : []);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load team");
    }
  }, [accessToken, tenantId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreateInvite(e: FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    setMessage(null);
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
      setMessage("Invite created.");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create invite");
    } finally {
      setPending(false);
    }
  }

  async function onRemoveMember(userId: string, memberEmail: string) {
    if (
      !window.confirm(
        `Remove access for ${memberEmail}?\n\nThey will no longer be able to sign in to this organisation.`,
      )
    ) {
      return;
    }
    setBusyUserId(userId);
    setError(null);
    setMessage(null);
    try {
      await apiClient.delete("/auth/members/" + encodeURIComponent(userId), {
        accessToken,
        clientId: tenantId,
      });
      setMessage(`Removed access for ${memberEmail}.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove member");
    } finally {
      setBusyUserId(null);
    }
  }

  async function onRevokeInvite(inviteId: string, inviteEmail: string) {
    if (!window.confirm(`Revoke pending invite for ${inviteEmail}?`)) {
      return;
    }
    setBusyInviteId(inviteId);
    setError(null);
    setMessage(null);
    try {
      await apiClient.delete("/auth/invites/" + encodeURIComponent(inviteId), {
        accessToken,
        clientId: tenantId,
      });
      setMessage(`Revoked invite for ${inviteEmail}.`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not revoke invite");
    } finally {
      setBusyInviteId(null);
    }
  }

  const pendingInvites = invites.filter((row) => !row.used_at);

  return (
    <div className="space-y-6">
      <p className="text-body-md text-muted-foreground">
        Manage who has org-admin access to this organisation. Copy invite links manually — SMTP is
        out of scope.
      </p>

      {error ? (
        <p className="text-body-md text-danger" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <Card className="border-primary/20 bg-primary/5">
          <CardContent className="py-4 text-body-md text-foreground">{message}</CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-border pb-4">
          <div>
            <CardTitle className="text-headline-sm">Members</CardTitle>
            <CardDescription>{members.length} with access</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {members.length === 0 ? (
            <p className="px-6 py-8 text-center text-muted-foreground">No members found.</p>
          ) : (
            <ul className="divide-y divide-border">
              {members.map((row) => {
                const isSelf = currentUserId === row.user_id;
                const isLast = members.length <= 1;
                return (
                  <li
                    key={row.user_id}
                    className="flex flex-col gap-3 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="font-medium text-foreground">
                        {row.display_name || row.email}
                        {isSelf ? (
                          <Badge variant="default" className="ml-2">
                            you
                          </Badge>
                        ) : null}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {row.email} · {row.role}
                        {row.joined_at ? ` · joined ${row.joined_at}` : ""}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      className="rounded-full"
                      disabled={isSelf || isLast || busyUserId === row.user_id}
                      title={
                        isSelf
                          ? "You cannot remove your own access"
                          : isLast
                            ? "Cannot remove the last member"
                            : undefined
                      }
                      onClick={() => void onRemoveMember(row.user_id, row.email)}
                    >
                      {busyUserId === row.user_id ? "Removing…" : "Remove access"}
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-border pb-4">
          <div>
            <CardTitle className="text-headline-sm">Pending invites</CardTitle>
            <CardDescription>{pendingInvites.length} awaiting acceptance</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {pendingInvites.length === 0 ? (
            <p className="px-6 py-8 text-center text-muted-foreground">No pending invites.</p>
          ) : (
            <ul className="divide-y divide-border">
              {pendingInvites.map((row) => (
                <li
                  key={row.id}
                  className="flex flex-col gap-3 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="font-medium text-foreground">{row.email}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      <Badge variant="warning" className="mr-2">
                        pending
                      </Badge>
                      {row.expires_at ? `expires ${row.expires_at}` : ""}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    className="rounded-full"
                    disabled={busyInviteId === row.id}
                    onClick={() => void onRevokeInvite(row.id, row.email)}
                  >
                    {busyInviteId === row.id ? "Revoking…" : "Revoke"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-headline-sm">Invite org admin</CardTitle>
          <CardDescription>
            Create a magic link for a colleague — copy and share manually.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(ev) => void onCreateInvite(ev)} className="space-y-4">
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
            <Button type="submit" disabled={pending} className="rounded-full">
              {pending ? "Creating…" : "Create invite link"}
            </Button>
          </form>
          {lastUrl ? (
            <Card className="mt-4 border-primary/20 bg-primary/5">
              <CardHeader className="pb-2">
                <CardTitle className="text-headline-sm">Copy this URL now</CardTitle>
              </CardHeader>
              <CardContent>
                <code className="block break-all text-sm text-foreground">{lastUrl}</code>
              </CardContent>
            </Card>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
