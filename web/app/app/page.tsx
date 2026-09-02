import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import {
  IconAgent,
  IconBilling,
  IconKnowledge,
  IconSlack,
  IconTools,
  IconUsage,
  IconWorkflows,
} from "@/components/dashboard/icons";
import { PortalStatusBanners } from "@/components/PortalStatusBanners";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { sessionTenantId } from "@/lib/tenant";

const LINKS = [
  {
    href: "/app/agent",
    title: "Agent settings",
    text: "Name, instructions, channel allowlist, and job schedules.",
    icon: IconAgent,
  },
  {
    href: "/app/tools",
    title: "Tools",
    text: "Register CLI tools and MCP servers for the agent.",
    icon: IconTools,
  },
  {
    href: "/app/knowledge",
    title: "Knowledge",
    text: "Upload documents, ingest status, and Slack history sync.",
    icon: IconKnowledge,
  },
  {
    href: "/app/workflows",
    title: "Workflows",
    text: "Shared workflow library from Slack uploads.",
    icon: IconWorkflows,
  },
  {
    href: "/app/billing",
    title: "Billing",
    text: "Subscribe, manage payment method, or cancel.",
    icon: IconBilling,
  },
  {
    href: "/app/usage",
    title: "Usage",
    text: "Mentions, jobs, errors, and token budgets.",
    icon: IconUsage,
  },
  {
    href: "/app/slack",
    title: "Slack",
    text: "Connect your workspace and check install status.",
    icon: IconSlack,
  },
] as const;

export default async function OrgAppHome() {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);

  return (
    <>
      <PageHeader
        className="mb-8"
        title="Overview"
        description="Configure your agent, upload knowledge, and review usage — without waiting on the platform owner."
      />
      <PortalStatusBanners
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
      <Card>
        <CardHeader>
          <CardTitle>Quick access</CardTitle>
          <CardDescription>
            Jump to agent setup, knowledge, billing, Slack, and other org settings.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {LINKS.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="group flex flex-col items-center rounded-lg border border-border bg-card px-3 py-5 text-center transition-colors hover:border-primary/30 hover:bg-muted"
                >
                  <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-[#f2f4f6] text-primary">
                    <Icon size={20} />
                  </span>
                  <span className="text-sm font-medium text-foreground">{item.title}</span>
                  <span className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                    {item.text}
                  </span>
                </Link>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </>
  );
}
