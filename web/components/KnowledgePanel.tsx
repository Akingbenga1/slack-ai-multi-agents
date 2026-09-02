"use client";

import { useState } from "react";
import { IngestJobsPanel } from "@/components/IngestJobsPanel";
import { SyncStatusPanel } from "@/components/SyncStatusPanel";
import { TenantFilesPanel } from "@/components/TenantFilesPanel";
import { UploadWidget } from "@/components/UploadWidget";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
  /** Slack connect page — defaults to org portal. */
  slackHref?: string;
};

export function KnowledgePanel({
  accessToken,
  tenantId,
  slackHref = "/app/slack",
}: Props) {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
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
        <TenantFilesPanel
          accessToken={accessToken}
          tenantId={tenantId}
          refreshKey={refreshKey}
        />
      </div>
      <div className="space-y-6">
        <SyncStatusPanel
          accessToken={accessToken}
          tenantId={tenantId}
          slackHref={slackHref}
        />
      </div>
    </div>
  );
}
