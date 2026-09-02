"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Building2 } from "lucide-react";
import { ApiError, apiClient } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type TenantSummary = {
  id: string;
  name: string;
  slug: string;
};

type Props = {
  accessToken: string | null;
  children: (tenantId: string) => ReactNode;
};

const selectClassName =
  "w-full max-w-md rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

export function AdminTenantScope({ accessToken, children }: Props) {
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [tenantId, setTenantId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadTenants = useCallback(async () => {
    if (!accessToken) {
      setLoading(false);
      setError("Sign in as platform owner to use this page.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<{ tenants: TenantSummary[] }>(
        "/admin/tenants",
        { accessToken, clientId: null },
      );
      const list = data?.tenants ?? [];
      setTenants(list);
      setTenantId((current) => current || (list[0]?.id ?? ""));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load tenants");
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void loadTenants();
  }, [loadTenants]);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
              <Building2 className="h-5 w-5" />
            </span>
            <div>
              <CardTitle className="text-headline-md">Tenant scope</CardTitle>
              <CardDescription className="mt-1">
                Host checks run in the context of the selected organisation.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-6">
          <label className="block max-w-md">
            <span className="text-sm font-medium text-foreground">Tenant</span>
            <select
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              disabled={loading}
              aria-label="Select tenant"
              className={`${selectClassName} mt-2`}
            >
              {tenants.length === 0 ? (
                <option value="">{loading ? "Loading…" : "No tenants"}</option>
              ) : (
                tenants.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.slug})
                  </option>
                ))
              )}
            </select>
          </label>
          {error ? (
            <p className="text-sm text-danger" role="alert">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>
      {tenantId ? children(tenantId) : null}
    </div>
  );
}
