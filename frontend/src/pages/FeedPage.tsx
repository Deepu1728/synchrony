import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Decision } from "../api/types";
import { FeedTable } from "../feed/FeedTable";
import { DECISION_LABEL } from "../feed/format";
import { useLiveFeed, type Filter } from "../feed/useLiveFeed";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "approve", label: "Approve" },
  { value: "review", label: "Review" },
  { value: "block", label: "Block" },
];

const STATUS_LABEL = { loading: "Loading", live: "Live", paused: "Paused", reconnecting: "Reconnecting" } as const;

export function FeedPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [paused, setPaused] = useState(false);
  const [pointing, setPointing] = useState(false);
  const { rows, status, error } = useLiveFeed(filter, paused || pointing);
  const navigate = useNavigate();

  const counts = useMemo(() => {
    const result: Record<Decision, number> = { approve: 0, review: 0, block: 0 };
    for (const row of rows) result[row.decision] += 1;
    return result;
  }, [rows]);

  return (
    <section>
      <div className="feed-head">
        <h1>Live feed</h1>
        <span className={`live live-${paused || pointing ? "paused" : status}`} role="status">
          <span className="live-dot" aria-hidden="true" />
          {paused ? "Paused" : pointing ? "Paused while you use the table" : STATUS_LABEL[status]}
        </span>
        <button className="button button-secondary" onClick={() => setPaused((p) => !p)}>
          {paused ? "Resume" : "Pause"}
        </button>
      </div>

      <div className="feed-controls">
        <div className="segmented" role="group" aria-label="Filter by decision">
          {FILTERS.map(({ value, label }) => (
            <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>
              {label}
            </button>
          ))}
        </div>
        <p className="muted feed-counts">
          Showing {rows.length} rows:{" "}
          {(Object.keys(counts) as Decision[]).map((d) => (
            <span key={d} className={`count count-${d}`}>{counts[d]} {DECISION_LABEL[d].toLowerCase()}</span>
          ))}
        </p>
      </div>

      {error && <p className="form-error" role="alert">Connection problem: {error}. Retrying every second.</p>}

      {rows.length > 0 ? (
        <div
          data-testid="feed-area"
          onMouseEnter={() => setPointing(true)}
          onMouseLeave={() => setPointing(false)}
          onFocus={() => setPointing(true)}
          onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) setPointing(false);
          }}
        >
          <FeedTable rows={rows} onOpen={(alertId) => navigate(`/alerts/${alertId}`)} />
        </div>
      ) : (
        <div className="card empty">
          {status === "loading" ? (
            <p className="muted">Loading transactions...</p>
          ) : (
            <>
              <p>No transactions to show yet.</p>
              <p className="muted">Start the simulator to see rows stream in:</p>
              <pre>cd backend && ../.venv/bin/python -m scripts.simulate --limit 300 --rate 10 --fraud-share 0.05</pre>
            </>
          )}
        </div>
      )}
    </section>
  );
}
