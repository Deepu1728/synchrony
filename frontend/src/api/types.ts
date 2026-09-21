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
