import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { BillingTabNav } from "@/components/billing/BillingTabNav";
import { orgBillingTabs } from "@/lib/billing-tabs";
import { BillingActions } from "@/components/BillingActions";
import { Card, CardContent } from "@/components/ui/card";
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
        className="mb-8"
        title="Billing"
        description="Pay for the organisation plan, or manage your subscription and payment method."
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          { label: "Billing" },
        ]}
      />
      {banner ? (
        <Card className="mb-6 border-primary/20 bg-primary/5">
          <CardContent className="py-4 text-body-md text-foreground">{banner}</CardContent>
        </Card>
      ) : null}
      <BillingTabNav tabs={orgBillingTabs()} />
      <div className="mt-6">
        <BillingActions
          accessToken={session?.accessToken ?? null}
          tenantId={tenantId}
          checkoutOutcome={checkoutOutcome}
        />
      </div>
    </>
  );
}
