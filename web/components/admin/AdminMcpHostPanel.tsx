"use client";

import { AdminTenantScope } from "@/components/admin/AdminTenantScope";
import { McpHostPanel } from "@/components/tools/McpHostPanel";

type Props = {
  accessToken: string | null;
};

export function AdminMcpHostPanel({ accessToken }: Props) {
  return (
    <AdminTenantScope accessToken={accessToken}>
      {(tenantId) => (
        <McpHostPanel accessToken={accessToken} tenantId={tenantId} />
      )}
    </AdminTenantScope>
  );
}
