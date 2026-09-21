import { api } from "./client";
import type { AlertDetail, FeedbackResult, SimilarResponse, Verdict } from "./types";

export const fetchAlert = (id: number, signal?: AbortSignal) => api<AlertDetail>(`/alerts/${id}`, { signal });

export const fetchSimilar = (id: number, signal?: AbortSignal) => api<SimilarResponse>(`/alerts/${id}/similar`, { signal });

export const regenerateExplanation = (id: number) => api<AlertDetail>(`/alerts/${id}/explain`, { method: "POST" });

export const submitFeedback = (alertId: number, verdict: Verdict, note?: string) =>
  api<FeedbackResult>("/feedback", {
    method: "POST",
    body: { alert_id: alertId, verdict, note: note?.trim() ? note.trim() : undefined },
  });
