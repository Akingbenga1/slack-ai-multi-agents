import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { BillingActions } from "@/components/BillingActions";
import { OrgNav } from "@/components/OrgNav";
import { sessionTenantId } from "@/lib/tenant";

type Props = {
  searchParams?: Promise<Record<string, string | string[] | undefined>> | Record<
    string,
    string | string[] | undefined
  >;
};

function param(
  value: string | string[] | undefined,
): string | undefined {
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
      "Checkout completed — plan activates when Stripe delivers checkout.session.completed (may take a few seconds).";
  } else if (checkout === "cancel") {
    banner = "Checkout canceled — no charge.";
  }

  const checkoutOutcome =
    checkout === "success" || checkout === "cancel" ? checkout : null;

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui, sans-serif", maxWidth: 720 }}>
      <h1 style={{ marginTop: 0 }}>Billing</h1>
      <p>
        Pay for the organisation plan via Stripe Checkout, or open the Customer
        Portal to update payment method / cancel (OR-02).
      </p>
      <p>
        Signed in as {session?.user?.email} ({session?.user?.role}
        {tenantId ? ` · tenant ${tenantId}` : ""})
      </p>
      {banner ? (
        <p
          style={{
            padding: "0.75rem 1rem",
            background: "#f5f5f5",
            borderRadius: 4,
          }}
        >
          {banner}
        </p>
      ) : null}
      <BillingActions
        accessToken={session?.accessToken ?? null}
        tenantId={tenantId}
        checkoutOutcome={checkoutOutcome}
      />
      <OrgNav current="billing" />
    </main>
  );
}
