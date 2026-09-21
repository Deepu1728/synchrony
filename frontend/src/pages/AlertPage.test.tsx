import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { makeAlert, makeSimilar } from "../test/fixtures";
import { AlertPage } from "./AlertPage";

vi.mock("../api/alerts", () => ({
  fetchAlert: vi.fn(),
  fetchSimilar: vi.fn(),
  regenerateExplanation: vi.fn(),
  submitFeedback: vi.fn(),
}));
import { fetchAlert, fetchSimilar, regenerateExplanation, submitFeedback } from "../api/alerts";
const alertMock = vi.mocked(fetchAlert);
const similarMock = vi.mocked(fetchSimilar);
const regenMock = vi.mocked(regenerateExplanation);
const feedbackMock = vi.mocked(submitFeedback);

function renderPage(path = "/alerts/12") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<p>Feed page</p>} />
        <Route path="/alerts/:id" element={<AlertPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  alertMock.mockReset();
  similarMock.mockReset();
  regenMock.mockReset();
  feedbackMock.mockReset();
});

describe("AlertPage", () => {
  it("shows all five parts of an alert plus the transaction", async () => {
    alertMock.mockResolvedValue(makeAlert());
    similarMock.mockResolvedValue(makeSimilar());
    renderPage();

    expect(await screen.findByRole("heading", { name: "Alert 12" })).toBeInTheDocument();
    expect(screen.getByTestId("alert-status")).toHaveTextContent("Open");
    for (const heading of ["Risk score", "Explanation", "What drove the score", "Rules that fired", "Similar past cases", "Review", "Transaction"]) {
      expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    }
    expect(screen.getByTestId("combined-score")).toHaveTextContent("0.88");
    expect(screen.getByTestId("shap-error_balance_orig")).toBeInTheDocument();
    expect(screen.getByText("FULL_BALANCE_DRAIN")).toBeInTheDocument();
    expect(await screen.findByTestId("similar-summary")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm fraud" })).toBeInTheDocument();
    expect(alertMock).toHaveBeenCalledWith(12, expect.anything());
    expect(similarMock).toHaveBeenCalledWith(12, expect.anything());
  });

  it("changes the status after a verdict and blocks a second one", async () => {
    alertMock.mockResolvedValueOnce(makeAlert());
    alertMock.mockResolvedValueOnce(makeAlert({
      status: "confirmed_fraud",
      feedback: { verdict: "fraud", username: "admin", note: null, created_at: "2026-09-22T11:00:00+00:00" },
    }));
    similarMock.mockResolvedValue(makeSimilar());
    feedbackMock.mockResolvedValue({ id: 1, alert_id: 12, verdict: "fraud", alert_status: "confirmed_fraud", case_added: true });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Confirm fraud" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, confirm fraud" }));

    expect(await screen.findByTestId("review-result")).toHaveTextContent("confirmed as fraud by admin");
    expect(screen.getByTestId("alert-status")).toHaveTextContent("Confirmed fraud");
    expect(screen.queryByRole("button", { name: "Confirm fraud" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark genuine" })).not.toBeInTheDocument();
    expect(feedbackMock).toHaveBeenCalledTimes(1);
  });

  it("updates the explanation badge after regenerating", async () => {
    alertMock.mockResolvedValue(makeAlert());
    similarMock.mockResolvedValue(makeSimilar());
    regenMock.mockResolvedValue(makeAlert({ explanation_source: "llm", explanation_text: "AI text here." }));
    renderPage();
    expect(await screen.findByTestId("explanation-source")).toHaveTextContent("Standard explanation");
    fireEvent.click(screen.getByRole("button", { name: "Regenerate with AI" }));
    expect(await screen.findByText("AI text here.")).toBeInTheDocument();
    expect(screen.getByTestId("explanation-source")).toHaveTextContent("AI-written");
  });

  it("shows a friendly page for an unknown alert", async () => {
    alertMock.mockRejectedValue(new ApiError(404, "Alert not found"));
    similarMock.mockRejectedValue(new ApiError(404, "Alert not found"));
    renderPage("/alerts/999");
    expect(await screen.findByRole("heading", { name: "Alert not found" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to the live feed/ })).toHaveAttribute("href", "/");
  });

  it("does not call the API for a malformed id", async () => {
    renderPage("/alerts/abc");
    expect(await screen.findByRole("heading", { name: "Alert not found" })).toBeInTheDocument();
    expect(alertMock).not.toHaveBeenCalled();
  });

  it("offers a retry when the alert cannot be loaded", async () => {
    alertMock.mockRejectedValueOnce(new ApiError(0, "Cannot reach the server"));
    similarMock.mockRejectedValueOnce(new ApiError(0, "Cannot reach the server"));
    alertMock.mockResolvedValue(makeAlert());
    similarMock.mockResolvedValue(makeSimilar());
    renderPage();
    expect(await screen.findByRole("heading", { name: "Could not load the alert" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach the server");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { name: "Alert 12" })).toBeInTheDocument();
  });

  it("still shows the alert when only the similar cases fail, and retries them", async () => {
    alertMock.mockResolvedValue(makeAlert());
    similarMock.mockRejectedValueOnce(new ApiError(500, "lookup failed"));
    similarMock.mockResolvedValue(makeSimilar());
    renderPage();
    expect(await screen.findByRole("heading", { name: "Alert 12" })).toBeInTheDocument();
    const section = (await screen.findByRole("heading", { name: "Similar past cases" })).closest("section")!;
    expect(await within(section).findByRole("alert")).toHaveTextContent("lookup failed");
    fireEvent.click(within(section).getByRole("button", { name: "Try again" }));
    expect(await screen.findByTestId("similar-summary")).toBeInTheDocument();
  });

  it("shows an already reviewed alert without review buttons", async () => {
    alertMock.mockResolvedValue(makeAlert({
      status: "false_positive",
      feedback: { verdict: "legit", username: "analyst", note: null, created_at: "2026-09-22T11:00:00+00:00" },
    }));
    similarMock.mockResolvedValue(makeSimilar());
    renderPage();
    expect(await screen.findByTestId("review-result")).toHaveTextContent("marked as genuine by analyst");
    expect(screen.getByTestId("alert-status")).toHaveTextContent("Marked genuine");
    expect(screen.queryByRole("button", { name: "Confirm fraud" })).not.toBeInTheDocument();
  });
});
