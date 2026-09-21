import { useState } from "react";
import { regenerateExplanation } from "../api/alerts";
import { ApiError } from "../api/client";
import type { AlertDetail } from "../api/types";

type Props = { alert: AlertDetail; onUpdated: (alert: AlertDetail) => void };

export function Explanation({ alert, onUpdated }: Props) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ tone: "info" | "error" | "ok"; text: string } | null>(null);
  const fromAi = alert.explanation_source === "llm";

  async function regenerate() {
    setBusy(true);
    setMessage(null);
    try {
      const updated = await regenerateExplanation(alert.id);
      onUpdated(updated);
      setMessage(
        updated.explanation_source === "llm"
          ? { tone: "ok", text: "New AI explanation written." }
          : {
              tone: "info",
              text: "The AI explanation is not available right now (no AI key is configured, or the AI answer was rejected by the safety checks). The standard explanation is shown.",
            },
      );
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof ApiError ? error.message : "Could not regenerate the explanation." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>Explanation</h2>
        <span className={`source ${fromAi ? "source-ai" : "source-standard"}`} data-testid="explanation-source">
          {fromAi ? "AI-written" : "Standard explanation"}
        </span>
      </div>
      <p className="explanation">{alert.explanation_text ?? "No explanation was stored for this alert."}</p>
      <div className="actions">
        <button className="button button-secondary" onClick={regenerate} disabled={busy}>
          {busy ? "Regenerating..." : "Regenerate with AI"}
        </button>
      </div>
      {message && (
        <p className={message.tone === "error" ? "form-error" : "note"} role={message.tone === "error" ? "alert" : "status"}>
          {message.text}
        </p>
      )}
    </section>
  );
}
