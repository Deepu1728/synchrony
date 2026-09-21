import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Health } from "../components/HealthBadge";

export function FeedPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Health>("/health")
      .then(setHealth)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Unexpected error"));
  }, []);

  return (
    <section>
      <h1>Live feed</h1>
      <p className="muted">The live transaction feed arrives in Step 4. For now this page confirms the API connection.</p>
      <div className="card">
        <h2>API health</h2>
        {error && <p className="error">{error}</p>}
        {health && <pre data-testid="health-json">{JSON.stringify(health, null, 2)}</pre>}
        {!health && !error && <p className="muted">Loading...</p>}
      </div>
    </section>
  );
}
