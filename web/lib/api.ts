/** Browser-facing FastAPI base (see NEXT_PUBLIC_API_BASE_URL). */
export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!raw) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  return raw.replace(/\/$/, "");
}

/** Auth headers: Bearer + session tenant only (never a foreign client id). */
export function apiAuthHeaders(
  accessToken: string,
  tenantId: string | null | undefined,
): Record<string, string> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
  };
  if (tenantId) {
    headers["X-Client-Id"] = tenantId;
  }
  return headers;
}
