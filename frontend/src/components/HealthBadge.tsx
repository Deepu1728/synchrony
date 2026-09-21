import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";

export type Health = { status: string; db: string };
type State = { kind: "loading" } | { kind: "ok"; health: Health } | { kind: "db-down" } | { kind: "down" };

const REFRESH_MS = 10_000;

export function useHealth(): State {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    const check = async () => {
      try {
        const health = await api<Health>("/health", { signal: controller.signal });
        setState({ kind: "ok", health });
      } catch (error) {
        if (controller.signal.aborted) return;
        setState(error instanceof ApiError && error.status === 503 ? { kind: "db-down" } : { kind: "down" });
      }
    };
    void check();
    const timer = setInterval(check, REFRESH_MS);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  return state;
}

export function HealthBadge() {
  const state = useHealth();
  const label = {
    loading: "Checking API...",
    ok: "API ok, database ok",
    "db-down": "API up, database down",
    down: "API unreachable",
  }[state.kind];
  const tone = { loading: "idle", ok: "ok", "db-down": "warn", down: "bad" }[state.kind];
  return (
    <span className={`health health-${tone}`} role="status">
      <span className="health-dot" aria-hidden="true" />
      {label}
    </span>
  );
}
