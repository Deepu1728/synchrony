import type { Reason } from "../api/types";
import { formatFeatureValue, formatSigned } from "./format";

export function ShapChart({ reasons }: { reasons: Reason[] }) {
  if (reasons.length === 0) {
    return <p className="muted">No factor breakdown was stored for this alert.</p>;
  }
  const largest = Math.max(...reasons.map((r) => Math.abs(r.shap)), 1e-9);
  return (
    <div className="shap">
      <div className="shap-legend">
        <span className="legend-genuine">&larr; pushes toward genuine</span>
        <span className="legend-fraud">pushes toward fraud &rarr;</span>
      </div>
      <ul className="shap-rows">
        {reasons.map((reason) => {
          const towardFraud = reason.shap > 0;
          const width = `${(Math.abs(reason.shap) / largest) * 100}%`;
          return (
            <li key={reason.feature} className="shap-row" data-testid={`shap-${reason.feature}`}>
              <div className="shap-label">
                <span>{reason.label}</span>
                <span className="mono muted">{formatFeatureValue(reason.value)}</span>
              </div>
              <div
                className="shap-track"
                role="img"
                aria-label={`${reason.label} is ${formatFeatureValue(reason.value)}: pushes toward ${towardFraud ? "fraud" : "genuine"} by ${Math.abs(reason.shap).toFixed(2)}`}
              >
                <div className="shap-half shap-neg">
                  {!towardFraud && <span className="shap-bar bar-genuine" data-testid="bar-genuine" style={{ width }} />}
                </div>
                <span className="shap-axis" />
                <div className="shap-half shap-pos">
                  {towardFraud && <span className="shap-bar bar-fraud" data-testid="bar-fraud" style={{ width }} />}
                </div>
              </div>
              <span className="mono shap-num">{formatSigned(reason.shap)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
