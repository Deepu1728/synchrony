import { useState } from "react";
import { submitFeedback } from "../api/alerts";
import { ApiError } from "../api/client";
import type { AlertDetail, Verdict } from "../api/types";
import { formatDateTime, VERDICT_TEXT } from "./format";

type Props = { alert: AlertDetail; onReviewed: () => Promise<void> };

const COPY: Record<Verdict, { button: string; title: string; effect: string; confirm: string }> = {
  fraud: {
    button: "Confirm fraud",
    title: "Confirm this alert as fraud?",
    effect: "The transaction is saved as a known fraud case, so similar future transactions are flagged more strictly.",
    confirm: "Yes, confirm fraud",
  },
  legit: {
    button: "Mark genuine",
    title: "Mark this alert as genuine?",
    effect: "The transaction is saved as a legitimate case, so similar future transactions are flagged less often.",
    confirm: "Yes, mark genuine",
  },
};

export function VerdictPanel({ alert, onReviewed }: Props) {
  const [pending, setPending] = useState<Verdict | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (alert.status !== "open") {
    const verdict = alert.status === "confirmed_fraud" ? "fraud" : "legit";
    return (
      <section className="card">
        <h2>Review</h2>
        <p className={`result result-${verdict}`} role="status" data-testid="review-result">
          This alert was {VERDICT_TEXT[verdict]}
          {alert.feedback && <> by {alert.feedback.username} on {formatDateTime(alert.feedback.created_at)}</>}.
        </p>
        {alert.feedback?.note && <p className="muted">Note: {alert.feedback.note}</p>}
        <p className="muted small">An alert can only be reviewed once.</p>
      </section>
    );
  }

  async function submit() {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      await submitFeedback(alert.id, pending, note);
      await onReviewed();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        await onReviewed().catch(() => undefined);
      } else {
        setError(err instanceof ApiError ? err.message : "Could not save your decision. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Review</h2>
      {pending === null ? (
        <>
          <p className="muted">Decide what this alert really was. You can do this once.</p>
          <div className="actions">
            <button className="button button-danger" onClick={() => setPending("fraud")}>{COPY.fraud.button}</button>
            <button className="button button-success" onClick={() => setPending("legit")}>{COPY.legit.button}</button>
          </div>
        </>
      ) : (
        <div className="confirm" role="group" aria-label="Confirm your decision">
          <h3>{COPY[pending].title}</h3>
          <p>{COPY[pending].effect}</p>
          <label className="field">
            <span>Note (optional)</span>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} rows={3} disabled={busy} />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="actions">
            <button className={`button ${pending === "fraud" ? "button-danger" : "button-success"}`} onClick={submit} disabled={busy}>
              {busy ? "Saving..." : COPY[pending].confirm}
            </button>
            <button className="button button-secondary" onClick={() => { setPending(null); setError(null); }} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
