import { useCallback, useEffect, useState } from "react";
import { fetchAlert, fetchSimilar } from "../api/alerts";
import { ApiError } from "../api/client";
import type { AlertDetail, SimilarResponse } from "../api/types";

export type Loadable<T> =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean }
  | { status: "ready"; data: T };

const failure = (error: unknown): Loadable<never> => ({
  status: "error",
  message: error instanceof ApiError ? error.message : "Unexpected error",
  notFound: error instanceof ApiError && error.status === 404,
});

export function useAlertDetail(id: number | null) {
  const [alert, setAlert] = useState<Loadable<AlertDetail>>({ status: "loading" });
  const [similar, setSimilar] = useState<Loadable<SimilarResponse>>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (id === null) {
      setAlert({ status: "error", message: "Alert not found", notFound: true });
      return;
    }
    const controller = new AbortController();
    setAlert({ status: "loading" });
    setSimilar({ status: "loading" });
    fetchAlert(id, controller.signal)
      .then((data) => setAlert({ status: "ready", data }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setAlert(failure(error));
      });
    fetchSimilar(id, controller.signal)
      .then((data) => setSimilar({ status: "ready", data }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setSimilar(failure(error));
      });
    return () => controller.abort();
  }, [id, attempt]);

  const replaceAlert = useCallback((data: AlertDetail) => setAlert({ status: "ready", data }), []);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { alert, similar, replaceAlert, reload };
}
