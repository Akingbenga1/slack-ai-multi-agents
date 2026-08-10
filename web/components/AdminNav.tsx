import Link from "next/link";
import type { CSSProperties } from "react";

const LINK_STYLE: CSSProperties = {
  marginRight: "0.75rem",
};

type Props = {
  current?: "home" | "tenants" | "health";
};

export function AdminNav({ current }: Props) {
  const items: { href: string; label: string; key: Props["current"] }[] = [
    { href: "/admin", label: "Home", key: "home" },
    { href: "/admin/tenants", label: "Tenants", key: "tenants" },
    { href: "/admin/health", label: "Health", key: "health" },
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
      <Link href="/">Site home</Link>
    </nav>
  );
}
