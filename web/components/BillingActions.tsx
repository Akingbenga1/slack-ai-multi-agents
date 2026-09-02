"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Props = {
  accessToken: string | null;
  tenantId: string | null;
  /** From `/app/billing?checkout=success|cancel` after checkout redirect. */
  checkoutOutcome?: "success" | "cancel" | null;
};

type BillingCustomer = {
  tenant_id: string;
  provider?: string | null;
  external_customer_id: string | null;
  external_subscription_id: string | null;
  plan_status: string;
  entitlements: Record<string, boolean>;
};

async function postSession(
  path: string,
  accessToken: string,
  tenantId: string | null,
): Promise<string> {
  const payload = await apiClient.post<{ url?: string }>(path, {
    accessToken,
    clientId: tenantId,
  });
  const url = payload?.url;
  if (!url) {
    throw new Error("API returned no checkout/portal URL");
  }
  return url;
}

async function fetchBillingMe(
  accessToken: string,
  tenantId: string | null,
): Promise<BillingCustomer | null> {
  return apiClient.get<BillingCustomer>("/billing/customers/me", {
    accessToken,
    clientId: tenantId,
    allowStatuses: [404],
  });
}

function planBadgeVariant(status: string): "success" | "warning" | "default" {
  const s = status.toLowerCase();
  if (s === "active") return "success";
  if (s === "inactive" || s === "past_due" || s === "canceled") return "warning";
  return "default";
}

export function BillingActions({
  accessToken,
  tenantId,
  checkoutOutcome = null,
}: Props) {
  const [pending, setPending] = useState<"checkout" | "portal" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [billing, setBilling] = useState<BillingCustomer | null | undefined>(undefined);
  const [waitingForWebhook, setWaitingForWebhook] = useState(checkoutOutcome === "success");

  const reload = useCallback(async () => {
    if (!accessToken) {
      setBilling(null);
      return null;
    }
    const row = await fetchBillingMe(accessToken, tenantId);
    setBilling(row);
    return row;
  }, [accessToken, tenantId]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    reload()
      .then((row) => {
        if (cancelled) return;
        if (checkoutOutcome === "success" && row?.plan_status === "active") {
          setWaitingForWebhook(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setBilling(null);
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reload, checkoutOutcome]);

  useEffect(() => {
    if (checkoutOutcome !== "success" || !accessToken) return;
    if (billing?.plan_status === "active") {
      setWaitingForWebhook(false);
      return;
    }
    setWaitingForWebhook(true);
    let attempts = 0;
    const id = window.setInterval(() => {
      attempts += 1;
      reload()
        .then((row) => {
          if (row?.plan_status === "active") {
            setWaitingForWebhook(false);
            window.clearInterval(id);
          } else if (attempts >= 8) {
            setWaitingForWebhook(false);
            window.clearInterval(id);
          }
        })
        .catch(() => {
          if (attempts >= 8) {
            setWaitingForWebhook(false);
            window.clearInterval(id);
          }
        });
    }, 2000);
    return () => window.clearInterval(id);
  }, [checkoutOutcome, accessToken, billing?.plan_status, reload]);

  async function start(kind: "checkout" | "portal") {
    setError(null);
    if (!accessToken) {
      setError(
        "No API token in session. Start the API (and seed demo users), then sign out and sign in again.",
      );
      return;
    }
    setPending(kind);
    try {
      const path =
        kind === "checkout" ? "/billing/checkout-session" : "/billing/portal-session";
      const url = await postSession(path, accessToken, tenantId);
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPending(null);
    }
  }

  const planActive = (billing?.plan_status || "").toLowerCase() === "active";
  const ents = billing?.entitlements;
  const entSummary = ents
    ? Object.entries(ents)
        .map(([k, v]) => `${k}:${v ? "on" : "off"}`)
        .join(" · ")
    : null;
  const stripeAdapter = (billing?.provider || "").toLowerCase() === "stripe";

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-headline-sm">Plan status</CardTitle>
          <CardDescription>
            Subscribe to activate agent features, ingest, and Slack sync entitlements.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {billing === undefined ? (
            <p className="text-body-md text-muted-foreground">Loading plan…</p>
          ) : billing === null ? (
            <p className="text-body-md text-muted-foreground">
              No billing customer yet — use <strong className="text-foreground">Pay</strong> to
              create one and start checkout.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-body-md text-muted-foreground">Plan status</span>
                <Badge variant={planBadgeVariant(billing.plan_status)}>
                  {billing.plan_status}
                </Badge>
                {billing.external_subscription_id ? (
                  <span className="text-sm text-muted-foreground">
                    sub {billing.external_subscription_id}
                  </span>
                ) : null}
              </div>
              {waitingForWebhook ? (
                <p className="text-body-md text-muted-foreground">
                  Waiting for payment confirmation to activate the plan…
                </p>
              ) : null}
              {!planActive && !waitingForWebhook ? (
                <p className="text-body-md text-muted-foreground">
                  Agent features stay off until the organisation plan is active. Pay below, or
                  manage your subscription if you already have a billing customer.
                </p>
              ) : null}
              {entSummary ? (
                <p className="text-sm text-muted-foreground">Entitlements: {entSummary}</p>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-3">
        <Button
          type="button"
          disabled={pending !== null}
          className="rounded-full"
          onClick={() => start("checkout")}
        >
          {pending === "checkout"
            ? "Starting checkout…"
            : planActive
              ? "Resubscribe / change plan"
              : "Pay"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          disabled={pending !== null}
          className="rounded-full"
          onClick={() => start("portal")}
        >
          {pending === "portal" ? "Opening…" : "Manage subscription"}
        </Button>
      </div>

      {error ? (
        <p className="text-body-md text-danger" role="alert">
          {error}
        </p>
      ) : null}

      <p className="text-sm text-muted-foreground">
        Requires payment provider keys in the API <code className="rounded bg-muted px-1">.env</code>
        . See <code className="rounded bg-muted px-1">docs/billing.md</code>.
        {stripeAdapter ? (
          <>
            {" "}
            Stripe adapter: <code className="rounded bg-muted px-1">STRIPE_SECRET_KEY</code>,{" "}
            <code className="rounded bg-muted px-1">STRIPE_PRICE_ID</code>,{" "}
            <code className="rounded bg-muted px-1">STRIPE_WEBHOOK_SECRET</code>.
          </>
        ) : null}
      </p>
    </div>
  );
}
