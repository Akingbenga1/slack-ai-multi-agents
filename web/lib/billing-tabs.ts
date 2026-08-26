export type BillingTab = {
  id: string;
  label: string;
  href: string;
};

export function adminTenantBillingTabs(tenantId: string): BillingTab[] {
  const base = `/admin/tenants/${tenantId}/billing`;
  return [
    { id: "overview", label: "Overview", href: base },
    { id: "invoices", label: "Invoices", href: `${base}/invoices` },
    { id: "transactions", label: "Transactions", href: `${base}/transactions` },
  ];
}

export function orgBillingTabs(): BillingTab[] {
  return [
    { id: "overview", label: "Plan & pay", href: "/app/billing" },
    { id: "invoices", label: "Invoices", href: "/app/billing/invoices" },
    { id: "transactions", label: "Transactions", href: "/app/billing/transactions" },
  ];
}
