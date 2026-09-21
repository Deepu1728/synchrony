import { Link } from "react-router-dom";
import type { Loadable } from "./useAlertDetail";
import type { SimilarResponse } from "../api/types";
import { formatAmount, TYPE_LABEL } from "../feed/format";
import { sourceLabel } from "./format";

type Props = { similar: Loadable<SimilarResponse>; onRetry: () => void };

export function SimilarCases({ similar, onRetry }: Props) {
  return (
    <section className="card">
      <h2>Similar past cases</h2>
      {similar.status === "loading" && <p className="muted">Looking up similar cases...</p>}
      {similar.status === "error" && (
        <div>
          <p className="form-error" role="alert">Could not load similar cases: {similar.message}</p>
          <button className="button button-secondary" onClick={onRetry}>Try again</button>
        </div>
      )}
      {similar.status === "ready" && <Cases data={similar.data} />}
    </section>
  );
}

function Cases({ data }: { data: SimilarResponse }) {
  const { summary, cases } = data;
  if (cases.length === 0) return <p className="muted">No similar cases were found.</p>;
  return (
    <>
      <p data-testid="similar-summary">
        <strong>{summary.fraud} of {cases.length}</strong> of the most similar past cases were fraud
        {summary.learned_fraud + summary.learned_legit > 0 &&
          ` (${summary.learned_fraud} confirmed fraud and ${summary.learned_legit} marked genuine by analysts)`}
        .
      </p>
      <div className="table-wrap small-table">
        <table className="feed-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Outcome</th>
              <th>Source</th>
              <th>Type</th>
              <th className="num">Amount</th>
              <th>Hour</th>
              <th className="num">Distance</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((c, index) => (
              <tr key={c.id} className={c.label === "fraud" ? "row-block" : "row-approve"} data-testid={`case-${c.id}`}>
                <td>{index + 1}</td>
                <td><span className={`badge ${c.label === "fraud" ? "badge-block" : "badge-approve"}`}>{c.label === "fraud" ? "Fraud" : "Genuine"}</span></td>
                <td>
                  {sourceLabel(c.source)}
                  {c.alert_id !== null && <> (<Link to={`/alerts/${c.alert_id}`}>alert {c.alert_id}</Link>)</>}
                </td>
                <td>{c.type ? (TYPE_LABEL[c.type] ?? c.type) : "-"}</td>
                <td className="num mono">{c.amount === null ? "-" : formatAmount(c.amount)}</td>
                <td className="mono">{c.hour === null ? "-" : String(c.hour).padStart(2, "0")}</td>
                <td className="num mono">{c.distance.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">Distance: smaller means more similar.</p>
    </>
  );
}
