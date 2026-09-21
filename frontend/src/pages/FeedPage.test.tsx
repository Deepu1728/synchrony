import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Decision, FeedRow } from "../api/types";
import { ApiError } from "../api/client";
import { BATCH_ROWS, MAX_ROWS, INITIAL_ROWS } from "../feed/useLiveFeed";
import { FeedPage } from "./FeedPage";

vi.mock("../api/feed", () => ({ fetchFeed: vi.fn() }));
import { fetchFeed } from "../api/feed";
const feedMock = vi.mocked(fetchFeed);

const row = (id: number, decision: Decision = "approve", extra: Partial<FeedRow> = {}): FeedRow => ({
  id,
  created_at: "2026-09-22T10:00:00+00:00",
  step: 5,
  type: "TRANSFER",
  amount: 1234.5,
  name_orig: "C111",
  name_dest: "C222",
  decision,
  score: 0.1,
  alert_id: decision === "approve" ? null : id + 1000,
  alert_status: decision === "approve" ? null : "open",
  true_label: null,
  ...extra,
});
const page = (items: FeedRow[], lastId: number | null = items.at(-1)?.id ?? null) => ({ items, last_id: lastId });

function AlertStub() {
  return <p>Alert detail {useParams().id}</p>;
}

function renderFeed() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<FeedPage />} />
        <Route path="/alerts/:id" element={<AlertStub />} />
      </Routes>
    </MemoryRouter>,
  );
}

const tick = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const rowIds = () => screen.getAllByTestId(/^row-/).map((el) => el.getAttribute("data-testid"));

beforeEach(() => {
  vi.useFakeTimers();
  feedMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("live feed", () => {
  it("loads the latest rows newest first, colour-coded by decision", async () => {
    feedMock.mockResolvedValueOnce(page([row(1), row(2, "review", { score: 0.42 }), row(3, "block", { score: 0.88 })]));
    feedMock.mockResolvedValue(page([], 3));
    renderFeed();
    expect(screen.getByText("Loading transactions...")).toBeInTheDocument();
    await tick(0);

    expect(rowIds()).toEqual(["row-3", "row-2", "row-1"]);
    expect(screen.getByTestId("row-3")).toHaveClass("row-block");
    expect(screen.getByTestId("row-2")).toHaveClass("row-review");
    expect(screen.getByTestId("row-1")).toHaveClass("row-approve");
    expect(screen.getByTestId("row-3")).toHaveTextContent("Block");
    expect(screen.getByTestId("row-3")).toHaveTextContent("0.88");
    expect(screen.getByTestId("row-3")).toHaveTextContent("Transfer");
    expect(screen.getByTestId("row-3")).toHaveTextContent("1,234.50");
    expect(screen.getByTestId("row-3")).toHaveTextContent("C111 → C222");
    expect(screen.getByRole("status")).toHaveTextContent("Live");
    expect(screen.getByText(/Showing 3 rows/)).toBeInTheDocument();
    expect(feedMock).toHaveBeenNthCalledWith(1, expect.objectContaining({ afterId: null, limit: INITIAL_ROWS, decision: undefined }));
  });

  it("polls every second from the last seen id and adds new rows on top", async () => {
    feedMock.mockResolvedValueOnce(page([row(1), row(2), row(3)]));
    feedMock.mockResolvedValueOnce(page([row(4, "block")]));
    feedMock.mockResolvedValue(page([], 4));
    renderFeed();
    await tick(0);
    expect(feedMock).toHaveBeenCalledTimes(1);

    await tick(1000);
    expect(feedMock).toHaveBeenNthCalledWith(2, expect.objectContaining({ afterId: 3, limit: BATCH_ROWS }));
    expect(rowIds()).toEqual(["row-4", "row-3", "row-2", "row-1"]);

    await tick(1000);
    expect(feedMock).toHaveBeenNthCalledWith(3, expect.objectContaining({ afterId: 4 }));
    await tick(1000);
    expect(feedMock).toHaveBeenNthCalledWith(4, expect.objectContaining({ afterId: 4 }));
    expect(rowIds()).toHaveLength(4);
  });

  it("pauses and resumes without losing its place", async () => {
    feedMock.mockResolvedValueOnce(page([row(1), row(2)]));
    feedMock.mockResolvedValue(page([], 2));
    renderFeed();
    await tick(0);

    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    await tick(0);
    expect(screen.getByRole("status")).toHaveTextContent("Paused");
    const callsWhenPaused = feedMock.mock.calls.length;
    await tick(5000);
    expect(feedMock).toHaveBeenCalledTimes(callsWhenPaused);

    feedMock.mockResolvedValueOnce(page([row(3, "review")]));
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    await tick(0);
    expect(feedMock).toHaveBeenLastCalledWith(expect.objectContaining({ afterId: 2 }));
    expect(rowIds()[0]).toBe("row-3");
    expect(screen.getByRole("status")).toHaveTextContent("Live");
  });

  it("filters by decision on the server and starts fresh", async () => {
    feedMock.mockResolvedValueOnce(page([row(1), row(2, "block")]));
    feedMock.mockResolvedValue(page([], 2));
    renderFeed();
    await tick(0);
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");

    feedMock.mockReset();
    feedMock.mockResolvedValueOnce(page([row(2, "block"), row(9, "block")]));
    feedMock.mockResolvedValue(page([], 9));
    fireEvent.click(screen.getByRole("button", { name: "Block" }));
    await tick(0);

    expect(feedMock).toHaveBeenNthCalledWith(1, expect.objectContaining({ afterId: null, decision: "block" }));
    expect(screen.getByRole("button", { name: "Block" })).toHaveAttribute("aria-pressed", "true");
    expect(rowIds()).toEqual(["row-9", "row-2"]);
    await tick(1000);
    expect(feedMock).toHaveBeenLastCalledWith(expect.objectContaining({ afterId: 9, decision: "block" }));
  });

  it("opens the alert when a flagged row is clicked or activated with the keyboard", async () => {
    feedMock.mockResolvedValueOnce(page([row(1), row(2, "review"), row(3, "block")]));
    feedMock.mockResolvedValue(page([], 3));
    renderFeed();
    await tick(0);

    const approve = screen.getByTestId("row-1");
    expect(approve).not.toHaveAttribute("tabindex");
    fireEvent.click(approve);
    expect(screen.queryByText(/Alert detail/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("row-2"));
    expect(screen.getByText("Alert detail 1002")).toBeInTheDocument();
  });

  it("supports the Enter key on flagged rows", async () => {
    feedMock.mockResolvedValueOnce(page([row(3, "block")]));
    feedMock.mockResolvedValue(page([], 3));
    renderFeed();
    await tick(0);
    const flagged = screen.getByTestId("row-3");
    expect(flagged).toHaveAttribute("tabindex", "0");
    fireEvent.keyDown(flagged, { key: "Enter" });
    expect(screen.getByText("Alert detail 1003")).toBeInTheDocument();
  });

  it("shows the alert status and simulator label", async () => {
    feedMock.mockResolvedValueOnce(page([
      row(1, "block", { alert_status: "confirmed_fraud", true_label: true }),
      row(2, "approve", { true_label: false }),
    ]));
    feedMock.mockResolvedValue(page([], 2));
    renderFeed();
    await tick(0);
    expect(screen.getByTestId("row-1")).toHaveTextContent("confirmed fraud");
    expect(screen.getByTestId("row-1")).toHaveTextContent("fraud");
    expect(screen.getByTestId("row-2")).toHaveTextContent("genuine");
  });

  it("keeps the rows, shows a connection problem and recovers", async () => {
    feedMock.mockResolvedValueOnce(page([row(1)]));
    feedMock.mockRejectedValueOnce(new ApiError(0, "Cannot reach the server"));
    feedMock.mockResolvedValue(page([row(2)], 2));
    renderFeed();
    await tick(0);

    await tick(1000);
    expect(screen.getByRole("alert")).toHaveTextContent("Connection problem: Cannot reach the server");
    expect(screen.getByRole("status")).toHaveTextContent("Reconnecting");
    expect(rowIds()).toEqual(["row-1"]);

    await tick(1000);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Live");
    expect(rowIds()).toEqual(["row-2", "row-1"]);
  });

  it("drains a full backlog immediately and keeps only the newest rows", async () => {
    const backlog = Array.from({ length: BATCH_ROWS }, (_, i) => row(i + 2));
    feedMock.mockResolvedValueOnce(page([row(1)]));
    feedMock.mockResolvedValueOnce(page(backlog));
    feedMock.mockResolvedValue(page([], BATCH_ROWS + 1));
    renderFeed();
    await tick(0);

    await tick(1000);
    expect(feedMock).toHaveBeenCalledTimes(3);
    expect(feedMock).toHaveBeenNthCalledWith(3, expect.objectContaining({ afterId: BATCH_ROWS + 1 }));
    expect(rowIds()).toHaveLength(MAX_ROWS);
    expect(rowIds()[0]).toBe(`row-${BATCH_ROWS + 1}`);
  });

  it("shows how to start the simulator when there is nothing yet", async () => {
    feedMock.mockResolvedValue(page([], null));
    renderFeed();
    await tick(0);
    expect(screen.getByText("No transactions to show yet.")).toBeInTheDocument();
    expect(screen.getByText(/scripts.simulate/)).toBeInTheDocument();
  });

  it("freezes the table while the pointer is on it, then catches up", async () => {
    feedMock.mockResolvedValueOnce(page([row(1), row(2, "block")]));
    feedMock.mockResolvedValue(page([], 2));
    renderFeed();
    await tick(0);

    fireEvent.mouseEnter(screen.getByTestId("feed-area"));
    await tick(0);
    expect(screen.getByRole("status")).toHaveTextContent("Paused while you use the table");
    const calls = feedMock.mock.calls.length;
    await tick(5000);
    expect(feedMock).toHaveBeenCalledTimes(calls);
    expect(rowIds()).toEqual(["row-2", "row-1"]);

    feedMock.mockResolvedValueOnce(page([row(3), row(4, "review")]));
    fireEvent.mouseLeave(screen.getByTestId("feed-area"));
    await tick(0);
    expect(feedMock).toHaveBeenLastCalledWith(expect.objectContaining({ afterId: 2 }));
    expect(rowIds()).toEqual(["row-4", "row-3", "row-2", "row-1"]);
    expect(screen.getByRole("status")).toHaveTextContent("Live");
  });

  it("also freezes while keyboard focus is inside the table", async () => {
    feedMock.mockResolvedValueOnce(page([row(1, "block")]));
    feedMock.mockResolvedValue(page([], 1));
    renderFeed();
    await tick(0);

    const flagged = screen.getByTestId("row-1");
    fireEvent.focus(flagged);
    await tick(0);
    const calls = feedMock.mock.calls.length;
    await tick(3000);
    expect(feedMock).toHaveBeenCalledTimes(calls);

    fireEvent.blur(flagged, { relatedTarget: document.body });
    await tick(1000);
    expect(feedMock.mock.calls.length).toBeGreaterThan(calls);
  });

  it("keeps asking from scratch while the feed is empty, then shows rows as they arrive", async () => {
    feedMock.mockResolvedValueOnce(page([], null));
    feedMock.mockResolvedValueOnce(page([], null));
    feedMock.mockResolvedValueOnce(page([row(1), row(2, "block")]));
    feedMock.mockResolvedValue(page([], 2));
    renderFeed();
    await tick(0);
    expect(screen.getByText("No transactions to show yet.")).toBeInTheDocument();

    await tick(1000);
    expect(feedMock).toHaveBeenNthCalledWith(2, expect.objectContaining({ afterId: null, limit: INITIAL_ROWS }));
    await tick(1000);
    expect(rowIds()).toEqual(["row-2", "row-1"]);
    await tick(1000);
    expect(feedMock).toHaveBeenLastCalledWith(expect.objectContaining({ afterId: 2 }));
  });

  it("stops polling when the page is closed", async () => {
    feedMock.mockResolvedValue(page([row(1)]));
    const { unmount } = renderFeed();
    await tick(0);
    unmount();
    const calls = feedMock.mock.calls.length;
    await tick(5000);
    expect(feedMock).toHaveBeenCalledTimes(calls);
  });
});
