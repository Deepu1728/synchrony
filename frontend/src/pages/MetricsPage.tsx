import { useSearchParams } from "react-router-dom";
import { DecisionBar } from "../metrics/DecisionBar";
import { formatCount, formatPercent } from "../metrics/format";
import { MetricCard } from "../metrics/MetricCard";
import { REFRESH_MS, useMetrics } from "../metrics/useMetrics";
import { formatTime } from "../feed/format";

const WINDOWS = [
  { key: "15", label: "15 min", minutes: 15 },
  { key: "60", label: "1 hour", minutes: 60 },
  { key: "1440", label: "24 hours", minutes: 1440 },
  { key: "all", label: "All time", minutes: null },
] as const;

export function MetricsPage() {
  const [params, setParams] = useSearchParams();
  const selected = WINDOWS.find((w) => w.key === params.get("window")) ?? WINDOWS[3];
  const { data, error, updatedAt, refresh } = useMetrics(selected.minutes);

  const gt = data?.ground_truth;
  const flagged = gt ? gt.fraud_flagged + gt.genuine_flagged : 0;
  const reviewed = data?.alerts.reviewed ?? 0;

  return (
    <section>
      <div className="feed-head">
        <h1>Metrics</h1>
        <span className="live live-live" style={{ flex: 1 }}>
          <span className="muted small">
            {updatedAt ? `Updated ${formatTime(updatedAt.toISOString())}` : "Loading..."} · refreshes every {REFRESH_MS / 1000} seconds
          </span>
        </span>
        <button className="button button-secondary" onClick={refresh}>Refresh</button>
      </div>

      <div className="feed-controls">
        <div className="segmented" role="group" aria-label="Time window">
          {WINDOWS.map(({ key, label }) => (
            <button key={key} aria-pressed={selected.key === key} onClick={() => setParams({ window: key }, { replace: true })}>
              {label}
            </button>
          ))}
        </div>
        {data && (
          <p className="muted feed-counts">
            {formatCount(data.decisions.total)} transactions, {formatCount(gt!.labelled)} with a simulator label
          </p>
        )}
      </div>

      {error && (
        <p className="form-error" role="alert">
          Could not load metrics: {error}.{data ? " Showing the last numbers received." : ""}{" "}
          {!data && <button className="button button-secondary" onClick={refresh}>Try again</button>}
        </p>
      )}

      {!data && !error && <p className="muted">Loading metrics...</p>}

      {data && gt && (
        <>
          <div className="metric-grid">
            <MetricCard
              testId="card-catch"
              title="Catch rate"
              help="Share of fraud that was sent to review or blocked."
              value={formatPercent(gt.catch_rate)}
              detail={gt.fraud_total > 0
                ? `${formatCount(gt.fraud_flagged)} of ${formatCount(gt.fraud_total)} fraud transactions flagged`
                : "No fraud transactions in this window."}
              extra={gt.fraud_total > 0 && `Blocked outright: ${formatPercent(gt.block_catch_rate)} (${formatCount(gt.fraud_blocked)} of ${formatCount(gt.fraud_total)})`}
            />
            <MetricCard
              testId="card-fpr"
              title="False-positive rate"
              help="Share of genuine transactions that were wrongly flagged."
              value={formatPercent(gt.false_positive_rate)}
              detail={gt.genuine_total > 0
                ? `${formatCount(gt.genuine_flagged)} of ${formatCount(gt.genuine_total)} genuine transactions flagged`
                : "No genuine transactions in this window."}
              extra={gt.genuine_total > 0 && `Wrongly blocked: ${formatPercent(gt.false_block_rate)} (${formatCount(gt.genuine_blocked)})`}
            />
            <MetricCard
              testId="card-precision"
              title="Precision"
              help="Of everything flagged, the share that was really fraud."
              value={formatPercent(gt.precision_flagged)}
              detail={flagged > 0
                ? `${formatCount(gt.fraud_flagged)} of ${formatCount(flagged)} flagged transactions were fraud`
                : "Nothing was flagged in this window."}
              extra={gt.precision_block !== null && `Block precision: ${formatPercent(gt.precision_block)}`}
            />
            <MetricCard
              testId="card-queue"
              title="Review queue"
              help="Alerts still waiting for an analyst decision."
              value={formatCount(data.alerts.open)}
              detail="alerts waiting for a decision"
              extra={reviewed > 0
                ? `Analysts decided ${formatCount(reviewed)}: ${formatCount(data.alerts.confirmed_fraud)} confirmed fraud, ${formatCount(data.alerts.false_positive)} marked genuine (${formatPercent(data.alerts.analyst_precision)} were real fraud)`
                : "No alerts have been reviewed in this window."}
            />
          </div>

          <div className="metric-lower">
            <section className="card">
              <h2>Decisions</h2>
              <DecisionBar decisions={data.decisions} />
            </section>
            <section className="card">
              <h2>Learning from analysts</h2>
              <p data-testid="learned">
                <strong>{formatCount(data.learned_cases.fraud + data.learned_cases.legit)}</strong> analyst-labelled cases
                ({formatCount(data.learned_cases.fraud)} fraud, {formatCount(data.learned_cases.legit)} genuine).
              </p>
              <p className="muted small">These labels change how similar future transactions are scored. This count covers all time.</p>
            </section>
          </div>

          <section className="card" data-testid="about">
            <h2>About these numbers</h2>
            <p className="muted">{data.note}</p>
            {gt.stream_fraud_share !== null && (
              <p className="muted">
                In this window {formatPercent(gt.stream_fraud_share)} of the labelled transactions are fraud. The simulator can send
                more fraud than real traffic normally contains, which makes precision look better than it would in production.
              </p>
            )}
          </section>
        </>
      )}
    </section>
  );
}
