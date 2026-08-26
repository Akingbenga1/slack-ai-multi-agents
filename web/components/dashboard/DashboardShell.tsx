"use client";

import Link from "next/link";
import { signOut } from "next-auth/react";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import styles from "./dashboard.module.css";
import { IconClose, IconMenu } from "./icons";

export type SidebarItem = {
  href: string;
  label: string;
  icon: ReactNode;
  /** Return true when this item should be marked active. */
  isActive?: (pathname: string) => boolean;
};

type Props = {
  brandTitle: string;
  brandSubtitle: string;
  brandMark: string;
  navLabel: string;
  items: SidebarItem[];
  footerItems?: SidebarItem[];
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
    <div className={styles.shell}>
      {open ? (
        <button
          type="button"
          className={styles.backdrop}
          aria-label="Close navigation menu"
          onClick={close}
        />
      ) : null}

      <aside
        id="dashboard-sidebar"
        className={`${styles.sidebar} ${open ? styles.sidebarOpen : ""}`}
        aria-label={navLabel}
      >
        <div className={styles.brand}>
          <div className={styles.brandMark} aria-hidden="true">
            {brandMark}
          </div>
          <div className={styles.brandText}>
            <p className={styles.brandTitle}>{brandTitle}</p>
            <p className={styles.brandSubtitle}>{brandSubtitle}</p>
          </div>
        </div>

        <nav className={styles.nav}>
          <p className={styles.navSectionLabel}>Menu</p>
          {items.map((item) => {
            const active = item.isActive
              ? item.isActive(pathname)
              : defaultIsActive(item.href, pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.navLink} ${active ? styles.navLinkActive : ""}`}
                aria-current={active ? "page" : undefined}
              >
                <span className={styles.navIcon}>{item.icon}</span>
                {item.label}
              </Link>
            );
          })}

          {footerItems.length > 0 ? (
            <>
              <p className={styles.navSectionLabel}>More</p>
              {footerItems.map((item) => {
                const active = item.isActive
                  ? item.isActive(pathname)
                  : defaultIsActive(item.href, pathname);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`${styles.navLink} ${active ? styles.navLinkActive : ""}`}
                  >
                    <span className={styles.navIcon}>{item.icon}</span>
                    {item.label}
                  </Link>
                );
              })}
            </>
          ) : null}
        </nav>

        {userEmail ? (
          <div className={styles.sidebarFooter}>
            <div className={styles.userCard}>
              <p className={styles.userEmail}>{userEmail}</p>
              {userRole ? <p className={styles.userRole}>{userRole.replace("_", " ")}</p> : null}
            </div>
            <button
              type="button"
              className={styles.signOutButton}
              onClick={() => void signOut({ callbackUrl: "/login" })}
            >
              Sign out
            </button>
          </div>
        ) : null}
      </aside>

      <div className={styles.main}>
        <header className={styles.topbar}>
          <button
            type="button"
            className={styles.menuButton}
            aria-expanded={open}
            aria-controls="dashboard-sidebar"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <IconClose size={20} /> : <IconMenu size={20} />}
          </button>
          <p className={styles.topbarTitle}>{activeItem?.label ?? brandTitle}</p>
        </header>
        <div className={styles.content}>{children}</div>
      </div>
    </div>
  );
}
