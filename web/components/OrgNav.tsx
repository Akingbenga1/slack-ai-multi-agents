"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { CSSProperties } from "react";

const LINK_STYLE: CSSProperties = {
  marginRight: "0.75rem",
};

const NAV_STYLE: CSSProperties = {
  marginBottom: "1.5rem",
  paddingBottom: "1rem",
  borderBottom: "1px solid #e5e5e5",
  fontSize: "0.95rem",
};

type NavKey =
  | "home"
  | "agent"
  | "knowledge"
  | "workflows"
  | "billing"
  | "usage"
  | "slack";

function currentFromPath(pathname: string): NavKey | undefined {
  if (pathname.startsWith("/app/agent")) return "agent";
  if (pathname.startsWith("/app/knowledge")) return "knowledge";
  if (pathname.startsWith("/app/workflows")) return "workflows";
  if (pathname.startsWith("/app/billing")) return "billing";
  if (pathname.startsWith("/app/usage")) return "usage";
  if (pathname.startsWith("/app/slack")) return "slack";
  if (pathname === "/app" || pathname === "/app/" || pathname.startsWith("/app/t/")) {
    return "home";
  }
  return undefined;
}

export function OrgNav() {
  const pathname = usePathname() || "";
  const current = currentFromPath(pathname);
  const items: { href: string; label: string; key: NavKey }[] = [
    { href: "/app", label: "Home", key: "home" },
    { href: "/app/agent", label: "Agent", key: "agent" },
    { href: "/app/knowledge", label: "Knowledge", key: "knowledge" },
    { href: "/app/workflows", label: "Workflows", key: "workflows" },
    { href: "/app/billing", label: "Billing", key: "billing" },
    { href: "/app/usage", label: "Usage", key: "usage" },
    { href: "/app/slack", label: "Slack", key: "slack" },
  ];

  return (
    <nav style={NAV_STYLE} aria-label="Organisation portal">
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={current === item.key ? "page" : undefined}
          style={{
            ...LINK_STYLE,
            fontWeight: current === item.key ? 600 : 400,
          }}
        >
          {item.label}
        </Link>
      ))}
      <Link href="/invite" style={LINK_STYLE}>
        Invite
      </Link>
      <Link href="/">Site home</Link>
    </nav>
  );
}
