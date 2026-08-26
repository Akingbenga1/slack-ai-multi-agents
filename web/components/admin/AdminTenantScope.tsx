"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import panel from "@/components/dashboard/panel.module.css";
import { ApiError, apiClient } from "@/lib/api";

type TenantSummary = {
  id: string;
  name: string;
  slug: string;
};

type Props = {
  accessToken: string | null;
  children: (tenantId: string) => ReactNode;
};

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
    <div className={panel.grid}>
      <section className={panel.section}>
        <label className={panel.formLabel}>
          Tenant
          <select
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            disabled={loading}
            aria-label="Select tenant"
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
        {error ? <p className={panel.error}>{error}</p> : null}
      </section>
      {tenantId ? children(tenantId) : null}
    </div>
  );
}
