import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { fetchMetrics } from "../api/metrics";
import type { Metrics } from "../api/types";

export const REFRESH_MS = 5000;

export function useMetrics(windowMinutes: number | null) {
  const [data, setData] = useState<Metrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setData(null);
    setError(null);
    setUpdatedAt(null);
  }, [windowMinutes]);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;

    const load = async () => {
      try {
        const metrics = await fetchMetrics(windowMinutes, controller.signal);
        if (controller.signal.aborted) return;
        setData(metrics);
        setUpdatedAt(new Date());
        setError(null);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Unexpected error");
      }
      timer = setTimeout(load, REFRESH_MS);
    };

    void load();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [windowMinutes, attempt]);

  const refresh = useCallback(() => setAttempt((n) => n + 1), []);
  return { data, error, updatedAt, refresh };
}
