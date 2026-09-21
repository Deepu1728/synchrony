import { api } from "./client";
import type { Decision, FeedResponse } from "./types";

type FeedQuery = {
  afterId: number | null;
  limit: number;
  decision?: Decision;
  signal?: AbortSignal;
};

export function fetchFeed({ afterId, limit, decision, signal }: FeedQuery): Promise<FeedResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (afterId !== null) params.set("after_id", String(afterId));
  if (decision) params.set("decision", decision);
  return api<FeedResponse>(`/transactions?${params}`, { signal });
}
