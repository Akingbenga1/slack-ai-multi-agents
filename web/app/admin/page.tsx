import Link from "next/link";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import styles from "@/components/dashboard/dashboard.module.css";
import {
  IconAgent,
  IconBilling,
  IconCliHost,
  IconHealth,
  IconMcpHost,
  IconTenants,
  IconTools,
} from "@/components/dashboard/icons";

export default async function AdminHome() {
  const session = await getServerSession(authOptions);

  return (
    <>
      <PageHeader
        title="Overview"
        description="Cross-tenant oversight — plan status, Slack connections, sync health, and support actions."
      />

      <div className={styles.cardGrid}>
        <Link href="/admin/tenants/new" className={`${styles.statCard} ${styles.statCardLink}`}>
          <span className={styles.statCardIcon}>
            <IconTenants size={22} />
          </span>
          <h2 className={styles.statCardTitle}>New tenant</h2>
          <p className={styles.statCardText}>
            Provision an organisation with org admin, billing, and default agent config (PO-04).
          </p>
        </Link>

        <Link href="/admin/tenants" className={`${styles.statCard} ${styles.statCardLink}`}>
          <span className={styles.statCardIcon}>
            <IconTenants size={22} />
          </span>
          <h2 className={styles.statCardTitle}>Tenants</h2>
          <p className={styles.statCardText}>
            List organisations and open detail views for plan, Slack, sync, and support actions.
          </p>
        </Link>

        <Link href="/admin/billing" className={`${styles.statCard} ${styles.statCardLink}`}>
          <span className={styles.statCardIcon}>
            <IconBilling size={22} />
          </span>
          <h2 className={styles.statCardTitle}>Billing</h2>
          <p className={styles.statCardText}>
            Cross-tenant billing overview, invoices, and transaction history.
          </p>
        </Link>

        <Link href="/admin/tools" className={`${styles.statCard} ${styles.statCardLink}`}>
          <span className={styles.statCardIcon}>
            <IconTools size={22} />
          </span>
          <h2 className={styles.statCardTitle}>Tools</h2>
          <p className={styles.statCardText}>
            Register CLI tools and MCP servers per tenant.
          </p>
        </Link>

        <Link href="/admin/cli-host" className={`${styles.statCard} ${styles.statCardLink}`}>
          <span className={styles.statCardIcon}>
            <IconCliHost size={22} />
          </span>
          <h2 className={styles.statCardTitle}>CLI host</h2>
          <p className={styles.statCardText}>
            Check and install registered CLI tools on this machine.
          </p>
        </Link>

        <Link href="/admin/mcp-host" className={`${styles.statCard} ${styles.statCardLink}`}>
          <span className={styles.statCardIcon}>
            <IconMcpHost size={22} />
          </span>
          <h2 className={styles.statCardTitle}>MCP host</h2>
          <p className={styles.statCardText}>
            Check that registered MCP servers are reachable and ready.
          </p>
        </Link>

        <Link href="/admin/agent-trace" className={`${styles.statCard} ${styles.statCardLink}`}>
          <span className={styles.statCardIcon}>
            <IconAgent size={22} />
          </span>
          <h2 className={styles.statCardTitle}>Agent trace</h2>
          <p className={styles.statCardText}>
            Run a request and inspect orchestrator prompts, plan steps, and executor answer.
          </p>
        </Link>

        <Link href="/admin/health" className={`${styles.statCard} ${styles.statCardLink}`}>
          <span className={styles.statCardIcon}>
            <IconHealth size={22} />
          </span>
          <h2 className={styles.statCardTitle}>Platform health</h2>
          <p className={styles.statCardText}>
            Compose service probes, job throughput, and recent error rates across the stack.
          </p>
        </Link>

        <div className={styles.statCard}>
          <span className={styles.statCardIcon} style={{ background: "rgba(148, 163, 184, 0.15)", color: "var(--muted)" }}>
            <IconTenants size={22} />
          </span>
          <h2 className={styles.statCardTitle}>Signed in</h2>
          <p className={styles.statCardText}>
            {session?.user?.email ?? "Unknown user"}
            {session?.user?.role ? ` · ${session.user.role.replace("_", " ")}` : ""}
          </p>
        </div>
      </div>
    </>
  );
}
