import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import panel from "@/components/dashboard/panel.module.css";
import { BillingTabNav } from "@/components/billing/BillingTabNav";
import { orgBillingTabs } from "@/lib/billing-tabs";
import { BillingActions } from "@/components/BillingActions";
import { sessionTenantId } from "@/lib/tenant";

type Props = {
  searchParams?: Promise<Record<string, string | string[] | undefined>> | Record<
    string,
    string | string[] | undefined
  >;
};

function param(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

export default async function BillingPage({ searchParams }: Props) {
  const session = await getServerSession(authOptions);
  const tenantId = sessionTenantId(session?.user?.tenantId);
  const params = (await searchParams) ?? {};
  const checkout = param(params.checkout);

  let banner: string | null = null;
  if (checkout === "success") {
    banner =
      "Payment completed — plan activates when the payment provider confirms (may take a few seconds).";
  } else if (checkout === "cancel") {
    banner = "Checkout canceled — no charge.";
  }

  const checkoutOutcome =
    checkout === "success" || checkout === "cancel" ? checkout : null;

  return (
    <>
      <PageHeader
        title="Billing"
        description="Pay for the organisation plan, or manage your subscription and payment method."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Billing" },
        ]}
      />
      {banner ? <p className={panel.infoBanner}>{banner}</p> : null}
      <BillingTabNav tabs={orgBillingTabs()} />
      <div className={panel.section}>
        <BillingActions
          accessToken={session?.accessToken ?? null}
          tenantId={tenantId}
          checkoutOutcome={checkoutOutcome}
        />
      </div>
    </>
  );
}
