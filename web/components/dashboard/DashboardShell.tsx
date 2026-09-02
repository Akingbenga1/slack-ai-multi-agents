"use client";

import Link from "next/link";
import { signOut } from "next-auth/react";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Bell, CircleHelp, Menu, Plus, Search, UserRound, X } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type SidebarItem = {
  href: string;
  label: string;
  icon: ReactNode;
  isActive?: (pathname: string) => boolean;
};

type PrimaryAction = {
  href: string;
  label: string;
};

type Props = {
  brandTitle: string;
  brandSubtitle: string;
  brandMark: string;
  navLabel: string;
  items: SidebarItem[];
  footerItems?: SidebarItem[];
  primaryAction?: PrimaryAction;
  userEmail?: string | null;
  userRole?: string | null;
  children: ReactNode;
};

function defaultIsActive(href: string, pathname: string): boolean {
  if (href === "/admin" || href === "/app") {
    return pathname === href || pathname === `${href}/`;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function DashboardShell({
  brandTitle,
  brandSubtitle,
  brandMark,
  navLabel,
  items,
  footerItems = [],
  primaryAction,
  userEmail,
  userRole,
  children,
}: Props) {
  const pathname = usePathname() || "";
  const [open, setOpen] = useState(false);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    close();
  }, [pathname, close]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  const activeItem =
    items.find((item) =>
      item.isActive ? item.isActive(pathname) : defaultIsActive(item.href, pathname),
    ) ?? items[0];

  return (
    <div className="min-h-screen bg-background lg:flex">
      {open ? (
        <button
          type="button"
          aria-label="Close navigation menu"
          className="fixed inset-0 z-40 bg-foreground/20 lg:hidden"
          onClick={close}
        />
      ) : null}

      <aside
        id="dashboard-sidebar"
        aria-label={navLabel}
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col border-r border-border bg-card transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-3 border-b border-border px-6 py-5">
          <div
            aria-hidden="true"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-sm font-semibold text-accent-foreground"
          >
            {brandMark}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">{brandTitle}</p>
            <p className="truncate text-xs text-muted-foreground">{brandSubtitle}</p>
          </div>
          <button
            type="button"
            className="ml-auto rounded-md p-1 text-muted-foreground hover:bg-muted lg:hidden"
            aria-label="Close menu"
            onClick={close}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {userEmail ? (
          <div className="border-b border-border px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <UserRound className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{userEmail}</p>
                {userRole ? (
                  <p className="truncate text-xs capitalize text-muted-foreground">
                    {userRole.replace(/_/g, " ")}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}

        {primaryAction ? (
          <div className="px-5 py-4">
            <Link
              href={primaryAction.href}
              className={cn(
                buttonVariants({ variant: "default", size: "lg" }),
                "w-full rounded-full",
              )}
            >
              <Plus className="h-4 w-4" />
              {primaryAction.label}
            </Link>
          </div>
        ) : null}

        <nav className="flex-1 overflow-y-auto px-4 py-2">
          <p className="px-3 py-2 text-label-md text-muted-foreground">Menu</p>
          {items.map((item) => {
            const active = item.isActive
              ? item.isActive(pathname)
              : defaultIsActive(item.href, pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "mb-1 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "border-l-2 border-primary bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <span className="shrink-0">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}

          {footerItems.length > 0 ? (
            <>
              <p className="mt-4 px-3 py-2 text-label-md text-muted-foreground">More</p>
              {footerItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="mb-1 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <span className="shrink-0">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </>
          ) : null}
        </nav>

        {userEmail ? (
          <div className="border-t border-border p-4">
            <Button
              type="button"
              variant="secondary"
              className="w-full"
              onClick={() => void signOut({ callbackUrl: "/login" })}
            >
              Sign out
            </Button>
          </div>
        ) : null}
      </aside>

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-4 border-b border-border bg-card px-4 py-3 lg:px-10">
          <button
            type="button"
            className="rounded-md p-2 text-muted-foreground hover:bg-muted lg:hidden"
            aria-expanded={open}
            aria-controls="dashboard-sidebar"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="hidden max-w-md flex-1 items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-body-md text-muted-foreground md:flex">
            <Search className="h-4 w-4 shrink-0" />
            <span>Search navigation</span>
          </div>

          <p className="truncate text-sm font-medium text-foreground md:hidden">
            {activeItem?.label ?? brandTitle}
          </p>

          <div className="ml-auto flex items-center gap-1">
            <button
              type="button"
              className="rounded-lg p-2 text-muted-foreground hover:bg-muted"
              aria-label="Notifications"
            >
              <Bell className="h-5 w-5" />
            </button>
            <button
              type="button"
              className="rounded-lg p-2 text-muted-foreground hover:bg-muted"
              aria-label="Help"
            >
              <CircleHelp className="h-5 w-5" />
            </button>
            <div
              className="ml-1 flex h-9 w-9 items-center justify-center rounded-full bg-accent text-accent-foreground"
              aria-hidden="true"
            >
              <UserRound className="h-4 w-4" />
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 lg:px-10 lg:py-10">
          {children}
        </main>
      </div>
    </div>
  );
}
