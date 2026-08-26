"use client";

import type { ReactNode } from "react";
import { DashboardShell, type SidebarItem } from "./DashboardShell";
import {
  IconAgent,
  IconBilling,
  IconDashboard,
  IconExternal,
  IconInvite,
  IconKnowledge,
  IconSlack,
  IconTools,
  IconUsage,
  IconWorkflows,
} from "./icons";

type Props = {
  userEmail?: string | null;
  userRole?: string | null;
  children: ReactNode;
};

const ORG_ITEMS: SidebarItem[] = [
  {
    href: "/app",
    label: "Overview",
    icon: <IconDashboard size={20} />,
    isActive: (pathname) =>
      pathname === "/app" || pathname === "/app/" || pathname.startsWith("/app/t/"),
  },
  {
    href: "/app/agent",
    label: "Agent",
    icon: <IconAgent size={20} />,
    isActive: (p) => p.startsWith("/app/agent"),
  },
  {
    href: "/app/tools",
    label: "Tools",
    icon: <IconTools size={20} />,
    isActive: (p) => p.startsWith("/app/tools"),
  },
  {
    href: "/app/knowledge",
    label: "Knowledge",
    icon: <IconKnowledge size={20} />,
    isActive: (p) => p.startsWith("/app/knowledge"),
  },
  {
    href: "/app/workflows",
    label: "Workflows",
    icon: <IconWorkflows size={20} />,
    isActive: (p) => p.startsWith("/app/workflows"),
  },
  {
    href: "/app/billing",
    label: "Billing",
    icon: <IconBilling size={20} />,
    isActive: (p) => p.startsWith("/app/billing"),
  },
  {
    href: "/app/usage",
    label: "Usage",
    icon: <IconUsage size={20} />,
    isActive: (p) => p.startsWith("/app/usage"),
  },
  {
    href: "/app/slack",
    label: "Slack",
    icon: <IconSlack size={20} />,
    isActive: (p) => p.startsWith("/app/slack"),
  },
];

const FOOTER_ITEMS: SidebarItem[] = [
  {
    href: "/app/invite",
    label: "Invite team",
    icon: <IconInvite size={20} />,
    isActive: (p) => p.startsWith("/app/invite"),
  },
  { href: "/", label: "Site home", icon: <IconExternal size={20} /> },
];

export function OrgDashboardShell({ userEmail, userRole, children }: Props) {
  return (
    <DashboardShell
      brandTitle="Org Portal"
      brandSubtitle="Client Slack AI Agents"
      brandMark="ORG"
      navLabel="Organisation portal navigation"
      items={ORG_ITEMS}
      footerItems={FOOTER_ITEMS}
      userEmail={userEmail}
      userRole={userRole}
    >
      {children}
    </DashboardShell>
  );
}
