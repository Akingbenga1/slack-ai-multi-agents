import Link from "next/link";
import type { ReactNode } from "react";
import { IconChevron } from "./icons";
import { cn } from "@/lib/utils";

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
  className?: string;
};

export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  children,
  className,
}: Props) {
  return (
    <header className={cn("mb-10", className)}>
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <ol
          aria-label="Breadcrumb"
          className="mb-3 flex flex-wrap items-center gap-1 text-body-md text-muted-foreground"
        >
          {breadcrumbs.map((crumb, i) => (
            <li key={`${crumb.label}-${i}`} className="flex items-center gap-1">
              {i > 0 ? (
                <span aria-hidden="true" className="text-border">
                  <IconChevron size={14} />
                </span>
              ) : null}
              {crumb.href ? (
                <Link href={crumb.href} className="hover:text-primary">
                  {crumb.label}
                </Link>
              ) : (
                <span aria-current="page" className="text-foreground">
                  {crumb.label}
                </span>
              )}
            </li>
          ))}
        </ol>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground lg:text-headline-lg">
            {title}
          </h1>
          {description ? (
            <p className="mt-2 max-w-3xl text-body-md text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </header>
  );
}

export function DashboardPanel({ children }: { children: ReactNode }) {
  return <div>{children}</div>;
}
