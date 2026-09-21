import { useEffect, useRef, useState } from "react";
import { fetchFeed } from "../api/feed";
import { ApiError } from "../api/client";
import type { Decision, FeedRow } from "../api/types";

export type Filter = Decision | "all";
export type FeedStatus = "loading" | "live" | "paused" | "reconnecting";

export const INITIAL_ROWS = 100;
export const BATCH_ROWS = 200;
export const MAX_ROWS = 200;
export const INTERVAL_MS = 1000;

export function useLiveFeed(filter: Filter, paused: boolean) {
  const [rows, setRows] = useState<FeedRow[]>([]);
  const [status, setStatus] = useState<FeedStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const cursor = useRef<number | null>(null);

  useEffect(() => {
    cursor.current = null;
    setRows([]);
    setStatus("loading");
    setError(null);
  }, [filter]);

  useEffect(() => {
    if (paused && cursor.current !== null) {
      setStatus("paused");
      return;
    }
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    const decision = filter === "all" ? undefined : filter;

    const poll = async () => {
      try {
        let more = true;
        while (more && !stopped) {
          const first = cursor.current === null;
          const limit = first ? INITIAL_ROWS : BATCH_ROWS;
          const feed = await fetchFeed({ afterId: cursor.current, limit, decision, signal: controller.signal });
          if (stopped) return;
          if (feed.items.length > 0) {
            setRows((previous) => [...[...feed.items].reverse(), ...previous].slice(0, MAX_ROWS));
          }
          cursor.current = feed.last_id ?? cursor.current;
          more = !first && feed.items.length === limit;
        }
        setStatus(paused ? "paused" : "live");
        setError(null);
      } catch (err) {
        if (stopped) return;
        setStatus("reconnecting");
        setError(err instanceof ApiError ? err.message : "Unexpected error");
      }
      if (!stopped && !paused) timer = setTimeout(poll, INTERVAL_MS);
    };

    void poll();
    return () => {
      stopped = true;
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [filter, paused]);

  return { rows, status, error };
}
