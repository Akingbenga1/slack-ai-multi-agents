"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { BillingTab } from "@/lib/billing-tabs";
import { cn } from "@/lib/utils";

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
    <nav
      aria-label="Billing sections"
      className="flex flex-wrap gap-2 border-b border-border pb-4"
    >
      {tabs.map((tab) => {
        const active = activeTab?.id === tab.id;
        return (
          <Link
            key={tab.id}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
