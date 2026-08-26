"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "@/components/billing/billing.module.css";
import type { BillingTab } from "@/lib/billing-tabs";

type Props = {
  tabs: BillingTab[];
};

export function BillingTabNav({ tabs }: Props) {
  const pathname = usePathname();

  const activeTab =
    tabs
      .filter(
        (tab) => pathname === tab.href || pathname.startsWith(`${tab.href}/`),
      )
      .sort((a, b) => b.href.length - a.href.length)[0] ?? null;

  return (
    <nav className={styles.tabNav} aria-label="Billing sections">
      {tabs.map((tab) => {
        const active = activeTab?.id === tab.id;
        return (
          <Link
            key={tab.id}
            href={tab.href}
            className={`${styles.tab} ${active ? styles.tabActive : ""}`}
            aria-current={active ? "page" : undefined}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
