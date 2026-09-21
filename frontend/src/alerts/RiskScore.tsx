import type { AlertDetail } from "../api/types";
import { DECISION_LABEL } from "../feed/format";
import { decisionFromScore } from "./format";

const pct = (value: number) => `${Math.min(Math.max(value, 0), 1) * 100}%`;

const PARTS = [
  { key: "model", label: "Model probability", help: "How fraud-like the transaction looks to the trained model." },
  { key: "similarity", label: "Similar-case share", help: "Share of the 10 most similar past cases that were fraud." },
  { key: "rules", label: "Rule score", help: "Combined weight of the rules that fired (shown for context)." },
  { key: "anomaly", label: "Anomaly percentile", help: "How unusual the transaction is against normal traffic (shown for context)." },
] as const;

export function RiskScore({ alert }: { alert: AlertDetail }) {
  const { scores, thresholds, decision } = alert;
  const byScore = decisionFromScore(scores.combined, thresholds.review, thresholds.block);
  return (
    <section className="card">
      <h2>Risk score</h2>
      <div className="risk-top">
        <span className="risk-number" data-testid="combined-score">{scores.combined.toFixed(2)}</span>
        <span className={`badge badge-${decision}`}>{DECISION_LABEL[decision]}</span>
      </div>

      <div className="gauge" role="img" aria-label={`Score ${scores.combined.toFixed(2)}; review from ${thresholds.review}, block from ${thresholds.block}`}>
        <div className="gauge-zones">
          <span className="zone zone-approve" style={{ width: pct(thresholds.review) }} />
          <span className="zone zone-review" style={{ width: pct(thresholds.block - thresholds.review) }} />
          <span className="zone zone-block" style={{ width: pct(1 - thresholds.block) }} />
        </div>
        <span className="gauge-needle" data-testid="gauge-needle" style={{ left: pct(scores.combined) }} />
        <span className="gauge-mark" data-testid="mark-review" style={{ left: pct(thresholds.review) }}>review {thresholds.review}</span>
        <span className="gauge-mark" data-testid="mark-block" style={{ left: pct(thresholds.block) }}>block {thresholds.block}</span>
      </div>

      {decision !== byScore && (
        <p className="note" role="note">
          The decision was set by a rule (see &ldquo;Rules that fired&rdquo;), not by the score alone.
        </p>
      )}

      <dl className="breakdown">
        {PARTS.map(({ key, label, help }) => (
          <div key={key} className="breakdown-row">
            <dt>
              {label}
              <span className="muted small">{help}</span>
            </dt>
            <dd>
              <span className="mini-bar" aria-hidden="true"><span style={{ width: pct(scores[key]) }} /></span>
              <span className="mono" data-testid={`part-${key}`}>{scores[key].toFixed(2)}</span>
            </dd>
          </div>
        ))}
      </dl>
      <p className="muted small">
        The combined score is a weighted mix of the model probability and the similar-case share. Rules can also force
        a review or block on their own.
      </p>
    </section>
  );
}
