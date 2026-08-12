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

type NavKey = "home" | "tenants" | "health";

function currentFromPath(pathname: string): NavKey | undefined {
  if (pathname.startsWith("/admin/tenants")) return "tenants";
  if (pathname.startsWith("/admin/health")) return "health";
  if (pathname === "/admin" || pathname === "/admin/") return "home";
  return undefined;
}

export function AdminNav() {
  const pathname = usePathname() || "";
  const current = currentFromPath(pathname);
  const items: { href: string; label: string; key: NavKey }[] = [
    { href: "/admin", label: "Home", key: "home" },
    { href: "/admin/tenants", label: "Tenants", key: "tenants" },
    { href: "/admin/health", label: "Health", key: "health" },
  ];

  return (
    <nav style={NAV_STYLE} aria-label="Platform admin">
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
      <Link href="/">Site home</Link>
    </nav>
  );
}
