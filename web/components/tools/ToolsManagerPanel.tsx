"use client";

import Link from "next/link";
import { Plus, Wrench } from "lucide-react";
import { TenantMcpServersPanel } from "@/components/tools/TenantMcpServersPanel";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  tenantLabel?: string;
  createHref?: string | null;
  accessToken?: string | null;
  tenantId?: string | null;
};

export function ToolsManagerPanel({
  tenantLabel,
  createHref = null,
  accessToken = null,
  tenantId = null,
}: Props) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="border-b border-border">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#ecfdf5] text-primary">
                <Wrench className="h-4 w-4" />
              </div>
              <div>
                <CardTitle className="text-headline-md">Tools</CardTitle>
                <CardDescription className="mt-1">
                  {tenantLabel
                    ? `Manage MCP servers available to ${tenantLabel}'s agent.`
                    : "Manage MCP servers available to the agent."}
                </CardDescription>
              </div>
            </div>
            {createHref ? (
              <Link
                href={createHref}
                className={cn(buttonVariants({ variant: "secondary" }), "rounded-full")}
              >
                <Plus className="h-4 w-4" />
                New CLI / HTTP tool
              </Link>
            ) : null}
          </div>
        </CardHeader>
      </Card>

      <TenantMcpServersPanel accessToken={accessToken} tenantId={tenantId} />
    </div>
  );
}
