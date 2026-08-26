import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./dashboard.module.css";
import { IconChevron } from "./icons";

type Crumb = {
  label: string;
  href?: string;
};

type Props = {
  title: string;
  description?: string;
  breadcrumbs?: Crumb[];
  actions?: ReactNode;
  children?: ReactNode;
};

export function PageHeader({ title, description, breadcrumbs, actions, children }: Props) {
  return (
    <header className={styles.pageHeader}>
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <ol className={styles.breadcrumbs} aria-label="Breadcrumb">
          {breadcrumbs.map((crumb, i) => (
            <li key={`${crumb.label}-${i}`} style={{ display: "contents" }}>
              {i > 0 ? (
                <span className={styles.breadcrumbSep} aria-hidden="true">
                  <IconChevron size={14} />
                </span>
              ) : null}
              {crumb.href ? (
                <Link href={crumb.href} className={styles.breadcrumbLink}>
                  {crumb.label}
                </Link>
              ) : (
                <span aria-current="page">{crumb.label}</span>
              )}
            </li>
          ))}
        </ol>
      ) : null}
      <div className={styles.pageHeaderMain}>
        <div className={styles.pageHeaderCopy}>
          <h1 className={styles.pageTitle}>{title}</h1>
          {description ? <p className={styles.pageDescription}>{description}</p> : null}
        </div>
        {actions ? <div className={styles.pageHeaderActions}>{actions}</div> : null}
      </div>
      {children}
    </header>
  );
}

export function DashboardPanel({ children }: { children: ReactNode }) {
  return <div className={styles.panel}>{children}</div>;
}
