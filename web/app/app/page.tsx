import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import styles from "@/components/dashboard/dashboard.module.css";
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
        title="Overview"
        description="Configure your agent, upload knowledge, and review usage — without waiting on the platform owner."
      />
      <PortalStatusBanners
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
      />
      <div className={styles.cardGrid}>
        {LINKS.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`${styles.statCard} ${styles.statCardLink}`}
          >
            <span className={styles.statCardIcon}>
              <item.icon size={22} />
            </span>
            <h2 className={styles.statCardTitle}>{item.title}</h2>
            <p className={styles.statCardText}>{item.text}</p>
          </Link>
        ))}
      </div>
    </>
  );
}
