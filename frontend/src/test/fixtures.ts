import type { AlertDetail, SimilarResponse } from "../api/types";

export const makeAlert = (over: Partial<AlertDetail> = {}): AlertDetail => ({
  id: 12,
  decision: "block",
  score: 0.88,
  status: "open",
  reasons: [
    { feature: "error_balance_orig", label: "sender balance mismatch", value: 0, shap: 0.89, direction: "increases_risk", text: "" },
    { feature: "oldbalanceOrg", label: "sender balance before", value: 692654.27, shap: 0.38, direction: "increases_risk", text: "" },
    { feature: "balance_drain_ratio", label: "share of sender balance sent", value: 1, shap: -0.15, direction: "decreases_risk", text: "" },
  ],
  rules: [{ code: "FULL_BALANCE_DRAIN", message: "Sends the sender's entire balance", weight: 0.6 }],
  explanation_text: "Blocked (risk score 0.88). Rules triggered: Sends the sender's entire balance.",
  explanation_source: "shap_fallback",
  created_at: "2026-09-22T10:00:00+00:00",
  transaction: {
    id: 900, step: 28, type: "TRANSFER", amount: 692654.27, name_orig: "C1231006815", name_dest: "C553264065",
    oldbalance_org: 692654.27, newbalance_orig: 0, oldbalance_dest: 0, newbalance_dest: 0, true_label: true,
    created_at: "2026-09-22T10:00:00+00:00",
  },
  scores: { model: 0.85, similarity: 1, anomaly: 0.96, rules: 0.8, combined: 0.88 },
  thresholds: { review: 0.3, block: 0.7 },
  feedback: null,
  ...over,
});

export const makeSimilar = (over: Partial<SimilarResponse> = {}): SimilarResponse => ({
  alert_id: 12,
  k: 10,
  cases: [
    { id: 1, label: "fraud", source: "paysim_train", distance: 0.0052, type: "TRANSFER", amount: 640000.5, hour: 4, note: null, alert_id: null },
    { id: 2, label: "fraud", source: "feedback", distance: 0.4, type: "CASH_OUT", amount: 88000, hour: 5, note: null, alert_id: 77 },
    { id: 3, label: "legit", source: "paysim_train", distance: 3.1, type: null, amount: null, hour: null, note: null, alert_id: null },
  ],
  summary: { fraud: 2, legit: 1, learned_fraud: 1, learned_legit: 0 },
  ...over,
});
