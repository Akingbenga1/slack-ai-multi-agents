import type { ReactNode } from "react";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { BillingTabNav } from "@/components/billing/BillingTabNav";
import { adminTenantBillingTabs } from "@/lib/billing-tabs";

type Crumb = {
  label: string;
  href?: string;
};

type Props = {
  tenantId: string;
  title: string;
  description: string;
  breadcrumbs: Crumb[];
  children: ReactNode;
};

export function AdminTenantBillingFrame({
  tenantId,
  title,
  description,
  breadcrumbs,
  children,
}: Props) {
  return (
    <>
      <PageHeader
        title={title}
        description={description}
        breadcrumbs={breadcrumbs}
      />
      <BillingTabNav tabs={adminTenantBillingTabs(tenantId)} />
      <div className="mt-8">{children}</div>
    </>
  );
}
