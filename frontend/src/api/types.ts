export type User = { username: string; role: string };

export type Token = {
  access_token: string;
  token_type: string;
  expires_in: number;
  role: string;
};

export type Decision = "approve" | "review" | "block";
export type AlertStatus = "open" | "confirmed_fraud" | "false_positive";

export type FeedRow = {
  id: number;
  created_at: string;
  step: number;
  type: string;
  amount: number;
  name_orig: string;
  name_dest: string;
  decision: Decision;
  score: number;
  alert_id: number | null;
  alert_status: AlertStatus | null;
  true_label: boolean | null;
};

export type FeedResponse = { items: FeedRow[]; last_id: number | null };

export type Reason = {
  feature: string;
  label: string;
  value: number;
  shap: number;
  direction: string;
  text: string;
};

export type RuleFlag = { code: string; message: string; weight: number };

export type TransactionDetail = {
  id: number;
  step: number;
  type: string;
  amount: number;
  name_orig: string;
  name_dest: string;
  oldbalance_org: number;
  newbalance_orig: number;
  oldbalance_dest: number;
  newbalance_dest: number;
  true_label: boolean | null;
  created_at: string;
};

export type ScoreBreakdown = { model: number; similarity: number; anomaly: number; rules: number; combined: number };
export type Thresholds = { review: number; block: number };
export type Verdict = "fraud" | "legit";
export type FeedbackInfo = { verdict: Verdict; username: string; note: string | null; created_at: string };

export type AlertDetail = {
  id: number;
  decision: Decision;
  score: number;
  status: AlertStatus;
  reasons: Reason[];
  rules: RuleFlag[];
  explanation_text: string | null;
  explanation_source: "llm" | "shap_fallback";
  created_at: string;
  transaction: TransactionDetail;
  scores: ScoreBreakdown;
  thresholds: Thresholds;
  feedback: FeedbackInfo | null;
};

export type SimilarCase = {
  id: number;
  label: Verdict;
  source: string;
  distance: number;
  type: string | null;
  amount: number | null;
  hour: number | null;
  note: string | null;
  alert_id: number | null;
};

export type SimilarResponse = {
  alert_id: number;
  k: number;
  cases: SimilarCase[];
  summary: { fraud: number; legit: number; learned_fraud: number; learned_legit: number };
};

export type FeedbackResult = { id: number; alert_id: number; verdict: Verdict; alert_status: AlertStatus; case_added: boolean };
