import type { AlertStatus, Decision } from "../api/types";

const amountFormat = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const timeFormat = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });

export const formatAmount = (amount: number): string => amountFormat.format(amount);

export const formatTime = (iso: string): string => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "-" : timeFormat.format(date);
};

export const formatScore = (score: number): string => score.toFixed(2);

export const DECISION_LABEL: Record<Decision, string> = {
  approve: "Approve",
  review: "Review",
  block: "Block",
};

export const ALERT_STATUS_LABEL: Record<AlertStatus, string> = {
  open: "open",
  confirmed_fraud: "confirmed fraud",
  false_positive: "false positive",
};

export const TYPE_LABEL: Record<string, string> = { TRANSFER: "Transfer", CASH_OUT: "Cash out" };
