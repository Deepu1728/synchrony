import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { Metrics } from "../api/types";
import { REFRESH_MS } from "../metrics/useMetrics";
import { MetricsPage } from "./MetricsPage";

vi.mock("../api/metrics", () => ({ fetchMetrics: vi.fn() }));
import { fetchMetrics } from "../api/metrics";
const metricsMock = vi.mocked(fetchMetrics);

const make = (over: Partial<Metrics> = {}): Metrics => ({
  window_minutes: null,
  decisions: { total: 3275, approve: 3180, review: 4, block: 91 },
  ground_truth: {
    labelled: 3275, fraud_total: 91, fraud_flagged: 91, fraud_blocked: 91,
    genuine_total: 3184, genuine_flagged: 4, genuine_blocked: 0,
    catch_rate: 1, block_catch_rate: 1, false_positive_rate: 0.0013, false_block_rate: 0,
    precision_flagged: 0.9579, precision_block: 1, stream_fraud_share: 0.0278,
  },
  alerts: { open: 70, confirmed_fraud: 24, false_positive: 1, reviewed: 25, analyst_precision: 0.96 },
  learned_cases: { fraud: 24, legit: 1 },
  note: "Rates use the simulator label.",
  ...over,
});

function renderPage(url = "/metrics") {
  return render(<MemoryRouter initialEntries={[url]}><MetricsPage /></MemoryRouter>);
}

const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

beforeEach(() => {
  vi.useFakeTimers();
  metricsMock.mockReset();
});
afterEach(() => vi.useRealTimers());

describe("MetricsPage", () => {
  it("shows the cards with the API numbers", async () => {
    metricsMock.mockResolvedValue(make());
    renderPage();
    await tick(0);
    expect(screen.getByTestId("card-catch-value")).toHaveTextContent("100%");
    expect(screen.getByText("91 of 91 fraud transactions flagged")).toBeInTheDocument();
    expect(screen.getByTestId("card-fpr-value")).toHaveTextContent("0.13%");
    expect(screen.getByText("4 of 3,184 genuine transactions flagged")).toBeInTheDocument();
    expect(screen.getByTestId("card-precision-value")).toHaveTextContent("95.8%");
    expect(screen.getByTestId("card-queue-value")).toHaveTextContent("70");
    expect(screen.getByTestId("decisions-block")).toHaveTextContent("91");
    expect(screen.getByTestId("decisions-review")).toHaveTextContent("4");
    expect(screen.getByTestId("learned")).toHaveTextContent("25 analyst-labelled cases");
    expect(screen.getByText("Rates use the simulator label.")).toBeInTheDocument();
  });

  it("defaults to all time and requests the chosen window", async () => {
    metricsMock.mockResolvedValue(make());
    renderPage();
    await tick(0);
    expect(metricsMock.mock.calls[0][0]).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "1 hour" }));
    await tick(0);
    expect(metricsMock.mock.calls.at(-1)![0]).toBe(60);
    expect(screen.getByRole("button", { name: "1 hour" })).toHaveAttribute("aria-pressed", "true");
  });

  it("reads the window from the URL", async () => {
    metricsMock.mockResolvedValue(make());
    renderPage("/metrics?window=15");
    await tick(0);
    expect(metricsMock.mock.calls[0][0]).toBe(15);
  });

  it("shows empty states when a window has no data", async () => {
    metricsMock.mockResolvedValue(make({
      decisions: { total: 0, approve: 0, review: 0, block: 0 },
      ground_truth: { ...make().ground_truth, labelled: 0, fraud_total: 0, fraud_flagged: 0, fraud_blocked: 0,
        genuine_total: 0, genuine_flagged: 0, catch_rate: null, block_catch_rate: null, false_positive_rate: null,
        false_block_rate: null, precision_flagged: null, precision_block: null, stream_fraud_share: null },
    }));
    renderPage();
    await tick(0);
    expect(screen.getByText("No transactions in this window.")).toBeInTheDocument();
    expect(screen.getByText("No fraud transactions in this window.")).toBeInTheDocument();
    expect(screen.getByText("No genuine transactions in this window.")).toBeInTheDocument();
    expect(screen.getByTestId("card-catch-value")).toHaveTextContent("-");
  });

  it("refreshes on a timer", async () => {
    metricsMock.mockResolvedValue(make());
    renderPage();
    await tick(0);
    await tick(REFRESH_MS);
    expect(metricsMock.mock.calls.length).toBe(2);
  });

  it("keeps old numbers when a refresh fails", async () => {
    metricsMock.mockResolvedValueOnce(make()).mockRejectedValue(new ApiError(0, "Cannot reach the server."));
    renderPage();
    await tick(0);
    await tick(REFRESH_MS);
    expect(screen.getByRole("alert")).toHaveTextContent("Showing the last numbers received");
    expect(screen.getByTestId("card-catch-value")).toHaveTextContent("100%");
  });

  it("offers retry when the first load fails", async () => {
    metricsMock.mockRejectedValueOnce(new ApiError(500, "Server error")).mockResolvedValue(make());
    renderPage();
    await tick(0);
    expect(screen.getByRole("alert")).toHaveTextContent("Server error");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await tick(0);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByTestId("card-catch-value")).toBeInTheDocument();
  });
});
