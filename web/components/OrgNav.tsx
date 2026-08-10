import Link from "next/link";
import type { CSSProperties } from "react";

const LINK_STYLE: CSSProperties = {
  marginRight: "0.75rem",
};

type Props = {
  current?: "home" | "agent" | "knowledge" | "workflows" | "billing" | "usage" | "slack";
};

export function OrgNav({ current }: Props) {
  const items: { href: string; label: string; key: Props["current"] }[] = [
    { href: "/app", label: "Home", key: "home" },
    { href: "/app/agent", label: "Agent", key: "agent" },
    { href: "/app/knowledge", label: "Knowledge", key: "knowledge" },
    { href: "/app/workflows", label: "Workflows", key: "workflows" },
    { href: "/app/billing", label: "Billing", key: "billing" },
    { href: "/app/usage", label: "Usage", key: "usage" },
    { href: "/app/slack", label: "Slack", key: "slack" },
  ];

  return (
    <nav
      style={{
        marginTop: "1.5rem",
        paddingTop: "1rem",
        borderTop: "1px solid #e5e5e5",
        fontSize: "0.95rem",
      }}
    >
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
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
