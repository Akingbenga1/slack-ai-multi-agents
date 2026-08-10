"use client";

import { useCallback, useEffect, useState } from "react";

export type AuthenticatedResourceState<T> = {
  /** `undefined` while loading; `null` when missing token or failed. */
  data: T | null | undefined;
  error: string | null;
  busy: boolean;
  reload: () => Promise<void>;
};

/**
 * Optional load/error/busy helper for portal panels (Sprint 30.2).
 * Loader is skipped when `accessToken` is null.
 */
export function useAuthenticatedResource<T>(
  accessToken: string | null | undefined,
  loader: (accessToken: string) => Promise<T>,
  deps: unknown[] = [],
): AuthenticatedResourceState<T> {
  const [data, setData] = useState<T | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    if (!accessToken) {
      setData(null);
      setError(null);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await loader(accessToken);
      setData(next);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps passed explicitly
  }, [accessToken, ...deps]);

  useEffect(() => {
    let cancelled = false;
    setData(undefined);
    if (!accessToken) {
      setData(null);
      return;
    }
    setBusy(true);
    setError(null);
    loader(accessToken)
      .then((next) => {
        if (!cancelled) setData(next);
      })
      .catch((err) => {
        if (!cancelled) {
          setData(null);
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps passed explicitly
  }, [accessToken, ...deps]);

  return { data, error, busy, reload };
}
