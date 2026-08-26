import type { ReactNode } from "react";
import { BillingTabNav } from "@/components/billing/BillingTabNav";
import { adminTenantBillingTabs } from "@/lib/billing-tabs";

type Props = {
  children: ReactNode;
  params: Promise<{ tenantId: string }> | { tenantId: string };
};

export default async function TenantBillingLayout({ children, params }: Props) {
  const { tenantId } = await params;

  return (
    <>
      <BillingTabNav tabs={adminTenantBillingTabs(tenantId)} />
      {children}
    </>
  );
}
