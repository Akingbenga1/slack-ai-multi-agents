/** Static mock fixtures for billing UI previews — not wired to the API. */

export type MockInvoice = {
  id: string;
  number: string;
  issuedAt: string;
  dueAt: string;
  amountCents: number;
  currency: string;
  status: "paid" | "open" | "void" | "uncollectible";
  periodStart: string;
  periodEnd: string;
};

export type MockTransaction = {
  id: string;
  occurredAt: string;
  type: "charge" | "refund" | "adjustment" | "payout";
  amountCents: number;
  currency: string;
  status: "succeeded" | "pending" | "failed";
  description: string;
  paymentMethod: string;
};

export type MockTenantBilling = {
  tenantId: string;
  tenantName: string;
  tenantSlug: string;
  provider: string;
  planStatus: string;
  planSource: string;
  externalCustomerId: string | null;
  externalSubscriptionId: string | null;
  mrrCents: number;
  currency: string;
  nextInvoiceAt: string | null;
  paymentMethodSummary: string | null;
};

export type MockPlatformBillingRow = MockTenantBilling & {
  lastPaymentAt: string | null;
  openInvoiceCount: number;
};

const DEMO_TENANT = "11111111-1111-1111-1111-111111111111";

const TENANT_NAMES: Record<string, { name: string; slug: string }> = {
  [DEMO_TENANT]: { name: "Demo Organisation", slug: "demo" },
};

function tenantMeta(tenantId: string): { name: string; slug: string } {
  if (TENANT_NAMES[tenantId]) return TENANT_NAMES[tenantId];
  const short = tenantId.slice(0, 8);
  return { name: `Organisation ${short}`, slug: `org-${short}` };
}

function hashSeed(input: string): number {
  let h = 0;
  for (let i = 0; i < input.length; i += 1) {
    h = (h * 31 + input.charCodeAt(i)) >>> 0;
  }
  return h;
}

export function getMockTenantBilling(tenantId: string): MockTenantBilling {
  const meta = tenantMeta(tenantId);

  if (tenantId === DEMO_TENANT) {
    return {
      tenantId,
      tenantName: meta.name,
      tenantSlug: meta.slug,
      provider: "stripe",
      planStatus: "active",
      planSource: "stripe",
      externalCustomerId: "cus_mock_demo",
      externalSubscriptionId: "sub_mock_demo",
      mrrCents: 4900,
      currency: "usd",
      nextInvoiceAt: "2026-09-01T00:00:00Z",
      paymentMethodSummary: "Visa •••• 4242",
    };
  }

  const seed = hashSeed(tenantId);
  const hasStripe = seed % 3 !== 0;
  const waived = seed % 5 === 0;

  return {
    tenantId,
    tenantName: meta.name,
    tenantSlug: meta.slug,
    provider: hasStripe ? "stripe" : "—",
    planStatus: waived || seed % 2 === 0 ? "active" : "inactive",
    planSource: waived ? "admin" : hasStripe ? "stripe" : "stripe",
    externalCustomerId: hasStripe ? `cus_mock_${meta.slug}` : null,
    externalSubscriptionId: hasStripe && !waived ? `sub_mock_${meta.slug}` : null,
    mrrCents: waived ? 0 : 4900,
    currency: "usd",
    nextInvoiceAt: hasStripe && !waived ? "2026-09-01T00:00:00Z" : null,
    paymentMethodSummary: hasStripe && !waived ? "Visa •••• 4242" : null,
  };
}

export function getMockInvoices(tenantId: string): MockInvoice[] {
  const meta = tenantMeta(tenantId);
  const billing = getMockTenantBilling(tenantId);
  if (!billing.externalCustomerId) return [];

  return [
    {
      id: `in_mock_${meta.slug}_003`,
      number: "INV-2026-0003",
      issuedAt: "2026-08-01T09:12:00Z",
      dueAt: "2026-08-08T09:12:00Z",
      amountCents: 4900,
      currency: "usd",
      status: "paid",
      periodStart: "2026-08-01T00:00:00Z",
      periodEnd: "2026-09-01T00:00:00Z",
    },
    {
      id: `in_mock_${meta.slug}_002`,
      number: "INV-2026-0002",
      issuedAt: "2026-07-01T09:12:00Z",
      dueAt: "2026-07-08T09:12:00Z",
      amountCents: 4900,
      currency: "usd",
      status: "paid",
      periodStart: "2026-07-01T00:00:00Z",
      periodEnd: "2026-08-01T00:00:00Z",
    },
    {
      id: `in_mock_${meta.slug}_001`,
      number: "INV-2026-0001",
      issuedAt: "2026-06-01T09:12:00Z",
      dueAt: "2026-06-08T09:12:00Z",
      amountCents: 4900,
      currency: "usd",
      status: billing.planSource === "admin" ? "void" : "paid",
      periodStart: "2026-06-01T00:00:00Z",
      periodEnd: "2026-07-01T00:00:00Z",
    },
  ];
}

export function getMockTransactions(tenantId: string): MockTransaction[] {
  const meta = tenantMeta(tenantId);
  const billing = getMockTenantBilling(tenantId);
  if (!billing.externalCustomerId) return [];

  const rows: MockTransaction[] = [
    {
      id: `txn_mock_${meta.slug}_003`,
      occurredAt: "2026-08-01T09:14:22Z",
      type: "charge",
      amountCents: 4900,
      currency: "usd",
      status: "succeeded",
      description: "Subscription renewal — Aug 2026",
      paymentMethod: "Visa •••• 4242",
    },
    {
      id: `txn_mock_${meta.slug}_002`,
      occurredAt: "2026-07-01T09:14:18Z",
      type: "charge",
      amountCents: 4900,
      currency: "usd",
      status: "succeeded",
      description: "Subscription renewal — Jul 2026",
      paymentMethod: "Visa •••• 4242",
    },
    {
      id: `txn_mock_${meta.slug}_001`,
      occurredAt: "2026-06-01T09:14:05Z",
      type: "charge",
      amountCents: 4900,
      currency: "usd",
      status: "succeeded",
      description: "Initial subscription — Jun 2026",
      paymentMethod: "Visa •••• 4242",
    },
  ];

  if (billing.planSource === "admin") {
    rows.unshift({
      id: `txn_mock_${meta.slug}_ref`,
      occurredAt: "2026-06-15T14:00:00Z",
      type: "adjustment",
      amountCents: 0,
      currency: "usd",
      status: "succeeded",
      description: "Admin payment waiver applied — billing paused",
      paymentMethod: "—",
    });
  }

  return rows;
}

export function getMockPlatformBillingOverview(): MockPlatformBillingRow[] {
  const demo = getMockTenantBilling(DEMO_TENANT);
  const rows: MockPlatformBillingRow[] = [
    {
      ...demo,
      lastPaymentAt: "2026-08-01T09:14:22Z",
      openInvoiceCount: 0,
    },
    {
      ...getMockTenantBilling("22222222-2222-2222-2222-222222222222"),
      lastPaymentAt: null,
      openInvoiceCount: 1,
    },
    {
      ...getMockTenantBilling("33333333-3333-3333-3333-333333333333"),
      lastPaymentAt: "2026-07-01T09:14:18Z",
      openInvoiceCount: 0,
    },
  ];
  return rows;
}

export function formatMoney(amountCents: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amountCents / 100);
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}
