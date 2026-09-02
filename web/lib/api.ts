/** Browser-facing FastAPI base (see NEXT_PUBLIC_API_BASE_URL). */
export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!raw) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  return raw.replace(/\/$/, "");
}

/**
 * Auth headers: Bearer + optional tenant.
 *
 * - **Org portal:** pass the session membership tenant (never a foreign id).
 * - **Platform admin list/health/audit:** pass `null` to omit `X-Client-Id`.
 * - **Platform admin acting on one tenant:** pass that tenant id as the target.
 */
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

/** Org-scoped call — session tenant as `X-Client-Id` when known. */
export function orgClientHeaders(
  accessToken: string,
  tenantId: string | null | undefined,
): Record<string, string> {
  return apiAuthHeaders(accessToken, tenantId);
}

/**
 * Platform-admin call — omit `X-Client-Id` unless `targetTenantId` is set
 * (e.g. tenant detail / status / budgets).
 */
export function adminClientHeaders(
  accessToken: string,
  targetTenantId?: string | null,
): Record<string, string> {
  return apiAuthHeaders(accessToken, targetTenantId ?? null);
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export type ApiRequestOptions = {
  accessToken: string;
  /**
   * Tenant for `X-Client-Id`. Use session tenant for org routes;
   * `null`/omit for admin list/health; target id for admin tenant actions.
   */
  clientId?: string | null;
  /** JSON body (sets Content-Type). Ignored when `body` is provided. */
  json?: unknown;
  /** Raw body (FormData, etc.) — do not set JSON Content-Type. */
  body?: BodyInit | null;
  /** Treat these HTTP statuses as soft misses (return null instead of throw). */
  allowStatuses?: number[];
};

function joinUrl(path: string): string {
  const base = getApiBaseUrl();
  if (!path.startsWith("/")) {
    return `${base}/${path}`;
  }
  return `${base}${path}`;
}

function detailFromBody(body: unknown, fallback: string): string {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (
      typeof detail === "object" &&
      detail !== null &&
      "message" in detail &&
      typeof (detail as { message: unknown }).message === "string"
    ) {
      return (detail as { message: string }).message;
    }
  }
  if (typeof body === "string" && body.trim()) {
    return body;
  }
  return fallback;
}

async function readBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function request<T>(
  method: string,
  path: string,
  opts: ApiRequestOptions,
): Promise<T | null> {
  const headers: Record<string, string> = {
    ...apiAuthHeaders(opts.accessToken, opts.clientId),
  };
  let body: BodyInit | undefined | null = opts.body;
  if (body === undefined && opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }

  const res = await fetch(joinUrl(path), {
    method,
    headers,
    body: body ?? undefined,
  });

  if (opts.allowStatuses?.includes(res.status)) {
    return null;
  }

  const payload = await readBody(res);
  if (!res.ok) {
    throw new ApiError(
      detailFromBody(payload, res.statusText || `HTTP ${res.status}`),
      res.status,
      payload,
    );
  }
  return payload as T;
}

/** Facade over FastAPI JSON calls (Sprint 30.2 / review §5.9). */
export const apiClient = {
  get<T>(path: string, opts: ApiRequestOptions): Promise<T | null> {
    return request<T>("GET", path, opts);
  },
  post<T>(path: string, opts: ApiRequestOptions): Promise<T | null> {
    return request<T>("POST", path, opts);
  },
  patch<T>(path: string, opts: ApiRequestOptions): Promise<T | null> {
    return request<T>("PATCH", path, opts);
  },
  delete<T = null>(path: string, opts: ApiRequestOptions): Promise<T | null> {
    return request<T>("DELETE", path, opts);
  },
};

export type DownloadFileOptions = {
  accessToken: string;
  clientId?: string | null;
  /** Suggested filename for the browser save dialog. */
  filename: string;
};

/** Fetch an authenticated file and trigger a browser download. */
export async function downloadAuthenticatedFile(
  path: string,
  opts: DownloadFileOptions,
): Promise<void> {
  const res = await fetch(joinUrl(path), {
    headers: apiAuthHeaders(opts.accessToken, opts.clientId),
  });

  if (!res.ok) {
    const payload = await readBody(res);
    throw new ApiError(
      detailFromBody(payload, res.statusText || `HTTP ${res.status}`),
      res.status,
      payload,
    );
  }

  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = opts.filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
