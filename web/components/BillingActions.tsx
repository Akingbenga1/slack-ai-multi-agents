"use client";

import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api";

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

export function BillingActions({
  accessToken,
  tenantId,
  checkoutOutcome = null,
}: Props) {
  const [pending, setPending] = useState<"checkout" | "portal" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [billing, setBilling] = useState<BillingCustomer | null | undefined>(
    undefined,
  );
  const [waitingForWebhook, setWaitingForWebhook] = useState(
    checkoutOutcome === "success",
  );

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

  // After checkout success, poll until webhook activates the plan (or timeout).
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
  const stripeAdapter =
    (billing?.provider || "").toLowerCase() === "stripe";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <div
        style={{
          padding: "0.75rem 1rem",
          background: "#f5f5f5",
          borderRadius: 4,
          fontSize: "0.95rem",
        }}
      >
        {billing === undefined ? (
          <p style={{ margin: 0 }}>Loading plan…</p>
        ) : billing === null ? (
          <p style={{ margin: 0 }}>
            No billing customer yet — use <strong>Pay</strong> to create one and
            start checkout (OR-02).
          </p>
        ) : (
          <>
            <p style={{ margin: "0 0 0.35rem" }}>
              Plan status:{" "}
              <strong style={{ color: planActive ? "#1b5e20" : "#9a3412" }}>
                {billing.plan_status}
              </strong>
              {billing.external_subscription_id
                ? ` · sub ${billing.external_subscription_id}`
                : ""}
            </p>
            {waitingForWebhook ? (
              <p style={{ margin: "0 0 0.35rem", color: "var(--muted)" }}>
                Waiting for payment confirmation to activate the plan…
              </p>
            ) : null}
            {!planActive && !waitingForWebhook ? (
              <p style={{ margin: "0 0 0.35rem", color: "var(--muted)" }}>
                Agent features stay off until the organisation plan is active.
                Pay below, or manage your subscription if you already have a
                billing customer.
              </p>
            ) : null}
            {entSummary ? (
              <p style={{ margin: 0, color: "#444" }}>Entitlements: {entSummary}</p>
            ) : null}
          </>
        )}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
        <button
          type="button"
          disabled={pending !== null}
          onClick={() => start("checkout")}
          style={{ padding: "0.5rem 1rem", cursor: "pointer" }}
        >
          {pending === "checkout"
            ? "Starting checkout…"
            : planActive
              ? "Resubscribe / change plan"
              : "Pay"}
        </button>
        <button
          type="button"
          disabled={pending !== null}
          onClick={() => start("portal")}
          style={{ padding: "0.5rem 1rem", cursor: "pointer" }}
        >
          {pending === "portal"
            ? "Opening…"
            : "Manage subscription"}
        </button>
      </div>
      {error ? (
        <p style={{ color: "var(--error)", margin: 0 }} role="alert">
          {error}
        </p>
      ) : null}
      <p style={{ color: "var(--muted)", margin: 0, fontSize: "0.9rem" }}>
        Requires payment provider keys in the API <code>.env</code>. See{" "}
        <code>docs/billing.md</code>.
        {stripeAdapter ? (
          <>
            {" "}
            Stripe adapter: <code>STRIPE_SECRET_KEY</code>,{" "}
            <code>STRIPE_PRICE_ID</code>, <code>STRIPE_WEBHOOK_SECRET</code>.
          </>
        ) : null}
      </p>
    </div>
  );
}
