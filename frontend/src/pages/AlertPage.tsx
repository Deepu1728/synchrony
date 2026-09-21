import { Link, useParams } from "react-router-dom";
import { fetchAlert } from "../api/alerts";
import { Explanation } from "../alerts/Explanation";
import { RiskScore } from "../alerts/RiskScore";
import { RulesList } from "../alerts/RulesList";
import { ShapChart } from "../alerts/ShapChart";
import { SimilarCases } from "../alerts/SimilarCases";
import { TransactionCard } from "../alerts/TransactionCard";
import { useAlertDetail } from "../alerts/useAlertDetail";
import { VerdictPanel } from "../alerts/VerdictPanel";
import { STATUS_TEXT } from "../alerts/format";
import { DECISION_LABEL } from "../feed/format";

export function AlertPage() {
  const params = useParams();
  const id = /^\d+$/.test(params.id ?? "") ? Number(params.id) : null;
  const { alert, similar, replaceAlert, reload } = useAlertDetail(id);

  const back = <p><Link to="/">&larr; Back to the live feed</Link></p>;

  if (alert.status === "loading") {
    return <section>{back}<p className="muted">Loading alert...</p></section>;
  }
  if (alert.status === "error") {
    return (
      <section>
        {back}
        <h1>{alert.notFound ? "Alert not found" : "Could not load the alert"}</h1>
        {!alert.notFound && (
          <>
            <p className="form-error" role="alert">{alert.message}</p>
            <button className="button" onClick={reload}>Try again</button>
          </>
        )}
      </section>
    );
  }

  const data = alert.data;
  const refresh = async () => replaceAlert(await fetchAlert(data.id));

  return (
    <section>
      {back}
      <div className="alert-head">
        <h1>Alert {data.id}</h1>
        <span className={`badge badge-${data.decision}`}>{DECISION_LABEL[data.decision]}</span>
        <span className={`tag tag-${data.status}`} data-testid="alert-status">{STATUS_TEXT[data.status]}</span>
      </div>

      <div className="alert-grid">
        <div className="alert-col">
          <RiskScore alert={data} />
          <Explanation alert={data} onUpdated={replaceAlert} />
          <section className="card">
            <h2>What drove the score</h2>
            <ShapChart reasons={data.reasons} />
          </section>
        </div>
        <div className="alert-col">
          <VerdictPanel alert={data} onReviewed={refresh} />
          <TransactionCard transaction={data.transaction} />
          <RulesList rules={data.rules} />
        </div>
      </div>

      <SimilarCases similar={similar} onRetry={reload} />
    </section>
  );
}
