"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Filter, Plus } from "lucide-react";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { TenantListPanel } from "@/components/TenantListPanel";
import { buttonVariants } from "@/components/ui/button";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Props = {
  accessToken: string | null;
};

export function AdminTenantsPageContent({ accessToken }: Props) {
  const [filterOpen, setFilterOpen] = useState(false);
  const [query, setQuery] = useState("");

  return (
    <>
      <PageHeader
        title="Tenants"
        description="Browse organisations — click a name for details, use the row menu for billing and access actions."
        actions={
          <>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setFilterOpen((open) => !open)}
              aria-expanded={filterOpen}
            >
              <Filter className="h-4 w-4" />
              Filter
            </Button>
            <Link
              href="/admin/tenants/new"
              className={cn(buttonVariants({ variant: "default" }), "rounded-full")}
            >
              <Plus className="h-4 w-4" />
              New tenant
            </Link>
          </>
        }
      />

      {filterOpen ? (
        <div className="mb-6">
          <label htmlFor="tenant-filter" className="sr-only">
            Filter tenants
          </label>
          <input
            id="tenant-filter"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by name or slug…"
            className="w-full max-w-md rounded-lg border border-border bg-card px-3 py-2 text-body-md text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
            autoFocus
          />
        </div>
      ) : null}

      <TenantListPanel accessToken={accessToken} query={query.trim().toLowerCase()} />
    </>
  );
}
