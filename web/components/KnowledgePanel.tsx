"use client";

import { useState } from "react";
import { IngestJobsPanel } from "@/components/IngestJobsPanel";
import { SyncStatusPanel } from "@/components/SyncStatusPanel";
import { UploadWidget } from "@/components/UploadWidget";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
};

export function KnowledgePanel({ accessToken, tenantId }: Props) {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <UploadWidget
        accessToken={accessToken}
        tenantId={tenantId}
        onUploaded={() => setRefreshKey((k) => k + 1)}
      />
      <IngestJobsPanel
        accessToken={accessToken}
        tenantId={tenantId}
        refreshKey={refreshKey}
      />
      <SyncStatusPanel accessToken={accessToken} tenantId={tenantId} />
    </div>
  );
}
