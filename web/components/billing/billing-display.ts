import type { MockInvoice, MockTransaction } from "@/lib/mock/billing-data";

export function invoiceStatusVariant(
  status: MockInvoice["status"],
): "success" | "warning" | "danger" | "muted" {
  if (status === "paid") return "success";
  if (status === "open") return "warning";
  if (status === "uncollectible") return "danger";
  return "muted";
}

export function transactionStatusVariant(
  status: MockTransaction["status"],
): "success" | "warning" | "danger" | "muted" {
  if (status === "succeeded") return "success";
  if (status === "pending") return "warning";
  if (status === "failed") return "danger";
  return "muted";
}

export function transactionTypeLabel(type: MockTransaction["type"]): string {
  if (type === "charge") return "Charge";
  if (type === "refund") return "Refund";
  if (type === "adjustment") return "Adjustment";
  return "Payout";
}

export function transactionTypeVariant(
  type: MockTransaction["type"],
): "default" | "success" | "warning" | "muted" {
  if (type === "charge") return "default";
  if (type === "refund") return "warning";
  if (type === "adjustment") return "muted";
  return "success";
}
