"use client";

import type { ReactNode } from "react";
import { DashboardShell, type SidebarItem } from "./DashboardShell";
import {
  IconAgent,
  IconBilling,
  IconDashboard,
  IconExternal,
  IconHealth,
  IconMcpHost,
  IconTenants,
  IconTools,
} from "./icons";

type Props = {
  userEmail?: string | null;
  userRole?: string | null;
  children: ReactNode;
};

const ADMIN_ITEMS: SidebarItem[] = [
  {
    href: "/admin",
    label: "Overview",
    icon: <IconDashboard size={20} />,
    isActive: (pathname) => pathname === "/admin" || pathname === "/admin/",
  },
  {
    href: "/admin/tenants",
    label: "Tenants",
    icon: <IconTenants size={20} />,
    isActive: (pathname) =>
      pathname.startsWith("/admin/tenants") &&
      !pathname.includes("/billing") &&
      !pathname.includes("/tools"),
  },
  {
    href: "/admin/billing",
    label: "Billing",
    icon: <IconBilling size={20} />,
    isActive: (pathname) =>
      pathname.startsWith("/admin/billing") || pathname.includes("/billing"),
  },
  {
    href: "/admin/tools",
    label: "Tools",
    icon: <IconTools size={20} />,
    isActive: (pathname) =>
      pathname.startsWith("/admin/tools") ||
      (pathname.includes("/tools") && !pathname.startsWith("/admin/mcp-host")),
  },
  {
    href: "/admin/mcp-host",
    label: "MCP host",
    icon: <IconMcpHost size={20} />,
    isActive: (pathname) => pathname.startsWith("/admin/mcp-host"),
  },
  {
    href: "/admin/agent-trace",
    label: "Agent trace",
    icon: <IconAgent size={20} />,
    isActive: (pathname) => pathname.startsWith("/admin/agent-trace"),
  },
  {
    href: "/admin/health",
    label: "Platform health",
    icon: <IconHealth size={20} />,
    isActive: (pathname) => pathname.startsWith("/admin/health"),
  },
];

const FOOTER_ITEMS: SidebarItem[] = [
  {
    href: "/",
    label: "Site home",
    icon: <IconExternal size={20} />,
  },
];

export function AdminDashboardShell({ userEmail, userRole, children }: Props) {
  return (
    <DashboardShell
      brandTitle="Platform Admin"
      brandSubtitle="Client Slack AI Agents"
      brandMark="CSA"
      navLabel="Platform admin navigation"
      items={ADMIN_ITEMS}
      footerItems={FOOTER_ITEMS}
      primaryAction={{ href: "/admin/tenants/new", label: "New tenant" }}
      userEmail={userEmail}
      userRole={userRole}
    >
      {children}
    </DashboardShell>
  );
}
