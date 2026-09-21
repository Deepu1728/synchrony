import type { Decision, Metrics } from "../api/types";
import { DECISION_LABEL } from "../feed/format";
import { formatCount, formatPercent, share } from "./format";

const ORDER: Decision[] = ["approve", "review", "block"];

export function DecisionBar({ decisions }: { decisions: Metrics["decisions"] }) {
  if (decisions.total === 0) {
    return <p className="muted">No transactions in this window.</p>;
  }
  return (
    <div data-testid="decision-bar">
      <div className="stack" role="img" aria-label={ORDER.map((d) => `${DECISION_LABEL[d]} ${formatCount(decisions[d])}`).join(", ")}>
        {ORDER.map((d) => (
          <span key={d} className={`stack-part fill-${d}`} style={{ width: `${share(decisions[d], decisions.total) * 100}%` }} />
        ))}
      </div>
      <ul className="stack-legend">
        {ORDER.map((d) => (
          <li key={d} data-testid={`decisions-${d}`}>
            <span className={`swatch fill-${d}`} aria-hidden="true" />
            <span className="stack-name">{DECISION_LABEL[d]}</span>
            <strong>{formatCount(decisions[d])}</strong>
            <span className="muted">{formatPercent(share(decisions[d], decisions.total))}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
