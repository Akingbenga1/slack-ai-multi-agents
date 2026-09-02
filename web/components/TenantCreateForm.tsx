"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Building2,
  Eye,
  EyeOff,
  Info,
  Mail,
  Lock,
  User,
  UserRound,
} from "lucide-react";
import { ApiError, apiClient } from "@/lib/api";
import { slugFromName } from "@/lib/slug";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  accessToken: string | null;
};

function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-foreground">{label}</span>
      {hint ? <span className="mt-1 block text-sm text-muted-foreground">{hint}</span> : null}
      <div className="mt-2">{children}</div>
    </label>
  );
}

const inputClassName =
  "w-full rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

export function TenantCreateForm({ accessToken }: Props) {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generatedPassword, setGeneratedPassword] = useState<string | null>(null);
  const [createdTenantId, setCreatedTenantId] = useState<string | null>(null);
  const [pendingRedirect, setPendingRedirect] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
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
      <Card>
        <CardContent className="py-8">
          <p className="text-body-md text-muted-foreground" role="status">
            Organisation created — opening tenant detail…
          </p>
        </CardContent>
      </Card>
    );
  }

  if (generatedPassword && createdTenantId) {
    return (
      <Card>
        <CardContent className="space-y-4 py-8">
          <div>
            <p className="text-headline-md text-foreground">Organisation created</p>
            <p className="mt-2 text-body-md text-muted-foreground">
              Save the generated org admin password now — it will not be shown again.
            </p>
          </div>
          <p className="rounded-lg border border-border bg-[#f8fafc] px-4 py-3 font-mono text-sm text-foreground">
            {generatedPassword}
          </p>
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/admin/tenants/${createdTenantId}`}
              className={buttonVariants({ variant: "default" })}
            >
              Open tenant detail
            </Link>
            <Link href="/admin/tenants" className={buttonVariants({ variant: "secondary" })}>
              Back to list
            </Link>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <section>
      {error ? (
        <p
          className="mb-6 rounded-lg border border-danger-muted bg-danger-muted/40 px-4 py-3 text-body-md text-danger"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      <form onSubmit={(ev) => void onSubmit(ev)} className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <Card>
            <CardHeader className="border-b border-border">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                  <Building2 className="h-5 w-5" />
                </span>
                <div>
                  <CardTitle>Organisation details</CardTitle>
                  <CardDescription>
                    Creates tenant row, org admin membership, billing customer, and default agent
                    config (PO-04). Slug is auto-filled from the name but can be edited — it is
                    permanent once created.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-5 pt-6">
              <FormField label="Organisation name">
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
                  className={inputClassName}
                  placeholder="Acme Co"
                />
              </FormField>

              <FormField
                label="Slug"
                hint="Auto-generated from name — edit to override. Cannot be changed later via API."
              >
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
                  className={inputClassName}
                />
              </FormField>

              <label className="flex items-start gap-3 rounded-lg border border-border bg-[#f8fafc] px-4 py-3">
                <input
                  type="checkbox"
                  checked={activatePlan}
                  onChange={(ev) => setActivatePlan(ev.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-border text-primary focus:ring-primary/30"
                />
                <span>
                  <span className="block text-sm font-medium text-foreground">
                    Activate plan locally
                  </span>
                  <span className="mt-0.5 block text-sm text-muted-foreground">
                    Demo; skip Stripe Checkout
                  </span>
                </span>
              </label>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b border-border">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                  <UserRound className="h-5 w-5" />
                </span>
                <div>
                  <CardTitle>Org admin</CardTitle>
                  <CardDescription>
                    Root org admin account for this organisation — used to sign in at /login and
                    manage the org portal.
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-5 pt-6">
              <FormField label="Org admin display name" hint="Optional">
                <div className="relative">
                  <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={adminDisplayName}
                    onChange={(ev) => setAdminDisplayName(ev.target.value)}
                    maxLength={255}
                    autoComplete="name"
                    className={cn(inputClassName, "pl-9")}
                    placeholder="Jane Doe"
                  />
                </div>
              </FormField>

              <FormField label="Org admin email">
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="email"
                    value={adminEmail}
                    onChange={(ev) => setAdminEmail(ev.target.value)}
                    required
                    autoComplete="off"
                    className={cn(inputClassName, "pl-9")}
                    placeholder="admin@example.com"
                  />
                </div>
              </FormField>

              <FormField
                label="Org admin password"
                hint="Optional — generated if blank (min 8 chars if set)"
              >
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type={showPassword ? "text" : "password"}
                    value={adminPassword}
                    onChange={(ev) => setAdminPassword(ev.target.value)}
                    minLength={8}
                    autoComplete="new-password"
                    className={cn(inputClassName, "pl-9 pr-10")}
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-muted-foreground hover:bg-muted"
                    onClick={() => setShowPassword((visible) => !visible)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </FormField>
            </CardContent>
          </Card>
        </div>

        <Card className="h-fit lg:sticky lg:top-24">
          <CardHeader className="border-b border-border">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#f2f4f6] text-muted-foreground">
                <Info className="h-5 w-5" />
              </span>
              <div>
                <CardTitle>Provisioning</CardTitle>
                <CardDescription>
                  What happens when you create an organisation through this form.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-6">
            <p className="text-body-md text-muted-foreground">
              Provision a new organisation with org admin, billing row, and default agent config.
            </p>
            <div className="rounded-lg border border-border bg-[#f8fafc] px-4 py-3 font-mono text-xs leading-relaxed text-foreground">
              <p>Tenant row</p>
              <p>Org admin membership</p>
              <p>Billing customer</p>
              <p>Default agent config</p>
            </div>
          </CardContent>
        </Card>

        <div className="flex flex-wrap justify-end gap-2 lg:col-span-2">
          <Link href="/admin/tenants" className={buttonVariants({ variant: "secondary" })}>
            Cancel
          </Link>
          <Button type="submit" disabled={creating || !accessToken} className="rounded-full">
            {creating ? "Creating…" : "Create organisation"}
          </Button>
        </div>
      </form>
    </section>
  );
}
