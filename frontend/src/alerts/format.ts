import type { AlertStatus, Decision, Verdict } from "../api/types";

export const formatFeatureValue = (value: number): string =>
  Number.isInteger(value)
    ? value.toLocaleString("en-US")
    : value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const formatSigned = (value: number): string => {
  const rounded = Math.abs(value).toFixed(2);
  if (value > 0 && rounded !== "0.00") return `+${rounded}`;
  if (value < 0 && rounded !== "0.00") return `−${rounded}`;
  return rounded;
};

const SOURCE_LABEL: Record<string, string> = {
  paysim_train: "Training data",
  feedback: "Analyst review",
  reported: "Customer report",
};
export const sourceLabel = (source: string): string => SOURCE_LABEL[source] ?? source;

export const STATUS_TEXT: Record<AlertStatus, string> = {
  open: "Open",
  confirmed_fraud: "Confirmed fraud",
  false_positive: "Marked genuine",
};

export const VERDICT_TEXT: Record<Verdict, string> = { fraud: "confirmed as fraud", legit: "marked as genuine" };

const dateTimeFormat = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "medium" });
export const formatDateTime = (iso: string): string => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "-" : dateTimeFormat.format(date);
};

export function decisionFromScore(score: number, review: number, block: number): Decision {
  if (score >= block) return "block";
  if (score >= review) return "review";
  return "approve";
}
