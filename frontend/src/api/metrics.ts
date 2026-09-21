import { api } from "./client";
import type { Metrics } from "./types";

export function fetchMetrics(windowMinutes: number | null, signal?: AbortSignal): Promise<Metrics> {
  const query = windowMinutes === null ? "" : `?window_minutes=${windowMinutes}`;
  return api<Metrics>(`/metrics${query}`, { signal });
}
