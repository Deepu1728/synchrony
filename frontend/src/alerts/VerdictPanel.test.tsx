import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { makeAlert } from "../test/fixtures";
import { VerdictPanel } from "./VerdictPanel";

vi.mock("../api/alerts", () => ({ submitFeedback: vi.fn() }));
import { submitFeedback } from "../api/alerts";
const feedbackMock = vi.mocked(submitFeedback);
const RESULT = { id: 1, alert_id: 12, verdict: "fraud" as const, alert_status: "confirmed_fraud" as const, case_added: true };

beforeEach(() => {
  feedbackMock.mockReset();
});

describe("VerdictPanel", () => {
  it("asks for confirmation before anything is saved, and can be cancelled", () => {
    render(<VerdictPanel alert={makeAlert()} onReviewed={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Confirm fraud" }));
    const group = screen.getByRole("group", { name: "Confirm your decision" });
    expect(group).toHaveTextContent("Confirm this alert as fraud?");
    expect(group).toHaveTextContent("known fraud case");
    expect(screen.getByLabelText("Note (optional)")).toHaveAttribute("maxlength", "500");
    expect(feedbackMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Confirm fraud" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark genuine" })).toBeInTheDocument();
  });

  it("saves a fraud verdict with the note, then refreshes the alert", async () => {
    feedbackMock.mockResolvedValue(RESULT);
    const onReviewed = vi.fn().mockResolvedValue(undefined);
    render(<VerdictPanel alert={makeAlert()} onReviewed={onReviewed} />);
    fireEvent.click(screen.getByRole("button", { name: "Confirm fraud" }));
    fireEvent.change(screen.getByLabelText("Note (optional)"), { target: { value: "confirmed by call" } });
    fireEvent.click(screen.getByRole("button", { name: "Yes, confirm fraud" }));
    await act(async () => {});
    expect(feedbackMock).toHaveBeenCalledWith(12, "fraud", "confirmed by call");
    expect(onReviewed).toHaveBeenCalledTimes(1);
  });

  it("saves a genuine verdict", async () => {
    feedbackMock.mockResolvedValue({ ...RESULT, verdict: "legit", alert_status: "false_positive" });
    const onReviewed = vi.fn().mockResolvedValue(undefined);
    render(<VerdictPanel alert={makeAlert()} onReviewed={onReviewed} />);
    fireEvent.click(screen.getByRole("button", { name: "Mark genuine" }));
    expect(screen.getByRole("group")).toHaveTextContent("Mark this alert as genuine?");
    fireEvent.click(screen.getByRole("button", { name: "Yes, mark genuine" }));
    await act(async () => {});
    expect(feedbackMock).toHaveBeenCalledWith(12, "legit", "");
    expect(onReviewed).toHaveBeenCalled();
  });

  it("locks the form while saving", async () => {
    let finish: (value: typeof RESULT) => void = () => {};
    feedbackMock.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    render(<VerdictPanel alert={makeAlert()} onReviewed={vi.fn().mockResolvedValue(undefined)} />);
    fireEvent.click(screen.getByRole("button", { name: "Confirm fraud" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, confirm fraud" }));
    expect(await screen.findByRole("button", { name: "Saving..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    await act(async () => finish(RESULT));
  });

  it("refreshes instead of erroring when someone else already reviewed the alert (409)", async () => {
    feedbackMock.mockRejectedValue(new ApiError(409, "Alert already reviewed"));
    const onReviewed = vi.fn().mockResolvedValue(undefined);
    render(<VerdictPanel alert={makeAlert()} onReviewed={onReviewed} />);
    fireEvent.click(screen.getByRole("button", { name: "Confirm fraud" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, confirm fraud" }));
    await act(async () => {});
    expect(onReviewed).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows other errors and lets the analyst try again", async () => {
    feedbackMock.mockRejectedValueOnce(new ApiError(500, "Server error"));
    feedbackMock.mockResolvedValueOnce(RESULT);
    const onReviewed = vi.fn().mockResolvedValue(undefined);
    render(<VerdictPanel alert={makeAlert()} onReviewed={onReviewed} />);
    fireEvent.click(screen.getByRole("button", { name: "Confirm fraud" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, confirm fraud" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Server error");
    expect(screen.getByRole("button", { name: "Yes, confirm fraud" })).toBeEnabled();
    expect(onReviewed).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Yes, confirm fraud" }));
    await act(async () => {});
    expect(onReviewed).toHaveBeenCalledTimes(1);
  });

  it("shows who reviewed a finished alert and offers no further verdict", () => {
    const alert = makeAlert({
      status: "confirmed_fraud",
      feedback: { verdict: "fraud", username: "admin", note: "called the customer", created_at: "2026-09-22T11:00:00+00:00" },
    });
    render(<VerdictPanel alert={alert} onReviewed={vi.fn()} />);
    expect(screen.getByTestId("review-result")).toHaveTextContent("This alert was confirmed as fraud by admin");
    expect(screen.getByText("Note: called the customer")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm fraud" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark genuine" })).not.toBeInTheDocument();
    expect(screen.getByText("An alert can only be reviewed once.")).toBeInTheDocument();
  });

  it("describes a genuine verdict and copes with a missing reviewer record", () => {
    render(<VerdictPanel alert={makeAlert({ status: "false_positive", feedback: null })} onReviewed={vi.fn()} />);
    expect(screen.getByTestId("review-result")).toHaveTextContent("This alert was marked as genuine.");
  });
});
