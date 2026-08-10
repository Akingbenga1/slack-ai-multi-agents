/**
 * Portal tenant helpers (Sprint 19.3 / OR-09).
 *
 * Org admins always use the session membership tenant. Query/path overrides
 * for a different client_id are rejected — never trusted from the URL.
 */

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isTenantUuid(value: string | null | undefined): boolean {
  return !!value && UUID_RE.test(value.trim());
}

/** Session tenant only — ignore URL/query spoofing. */
export function sessionTenantId(
  sessionTenant: string | null | undefined,
): string | null {
  const tid = (sessionTenant || "").trim();
  return isTenantUuid(tid) ? tid : null;
}

/**
 * True when a requested tenant matches the session (or request is empty).
 * Org A must not open Org B routes / send Org B ids.
 */
export function tenantMatchesSession(
  sessionTenant: string | null | undefined,
  requested: string | null | undefined,
): boolean {
  const allowed = sessionTenantId(sessionTenant);
  const req = (requested || "").trim();
  if (!req) return true;
  if (!allowed) return false;
  return req.toLowerCase() === allowed.toLowerCase();
}
