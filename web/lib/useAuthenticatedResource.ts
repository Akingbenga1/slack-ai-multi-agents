"use client";

import { useCallback, useEffect, useRef, useState } from "react";

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
 * Uses a generation counter so stale responses never overwrite newer loads.
 */
export function useAuthenticatedResource<T>(
  accessToken: string | null | undefined,
  loader: (accessToken: string) => Promise<T>,
  deps: unknown[] = [],
): AuthenticatedResourceState<T> {
  const [data, setData] = useState<T | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const generationRef = useRef(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(async () => {
    const gen = ++generationRef.current;
    if (!accessToken) {
      if (gen === generationRef.current) {
        setData(null);
        setError(null);
        setBusy(false);
      }
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await loaderRef.current(accessToken);
      if (gen !== generationRef.current) return;
      setData(next);
    } catch (err) {
      if (gen !== generationRef.current) return;
      setData(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      if (gen === generationRef.current) setBusy(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps passed explicitly
  }, [accessToken, ...deps]);

  useEffect(() => {
    const gen = ++generationRef.current;
    setData(undefined);
    if (!accessToken) {
      setData(null);
      setBusy(false);
      return;
    }
    setBusy(true);
    setError(null);
    loaderRef.current(accessToken)
      .then((next) => {
        if (gen !== generationRef.current) return;
        setData(next);
      })
      .catch((err) => {
        if (gen !== generationRef.current) return;
        setData(null);
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (gen === generationRef.current) setBusy(false);
      });
    return () => {
      // Invalidate in-flight resolution without bumping generation for reload.
      generationRef.current += 1;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps passed explicitly
  }, [accessToken, ...deps]);

  return { data, error, busy, reload };
}
