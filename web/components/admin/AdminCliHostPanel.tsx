"use client";

import { AdminTenantScope } from "@/components/admin/AdminTenantScope";
import { CliHostPanel } from "@/components/tools/CliHostPanel";

type Props = {
  accessToken: string | null;
};

export function AdminCliHostPanel({ accessToken }: Props) {
  return (
    <AdminTenantScope accessToken={accessToken}>
      {(tenantId) => (
        <CliHostPanel accessToken={accessToken} tenantId={tenantId} />
      )}
    </AdminTenantScope>
  );
}
