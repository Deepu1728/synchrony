import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { makeAlert } from "../test/fixtures";
import { Explanation } from "./Explanation";

vi.mock("../api/alerts", () => ({ regenerateExplanation: vi.fn() }));
import { regenerateExplanation } from "../api/alerts";
const regenMock = vi.mocked(regenerateExplanation);

beforeEach(() => {
  regenMock.mockReset();
});

describe("Explanation", () => {
  it("labels where the text came from", () => {
    const { rerender } = render(<Explanation alert={makeAlert()} onUpdated={() => {}} />);
    expect(screen.getByTestId("explanation-source")).toHaveTextContent("Standard explanation");
    expect(screen.getByText(/Blocked \(risk score 0.88\)/)).toBeInTheDocument();
    rerender(<Explanation alert={makeAlert({ explanation_source: "llm" })} onUpdated={() => {}} />);
    expect(screen.getByTestId("explanation-source")).toHaveTextContent("AI-written");
  });

  it("shows the new AI text when regeneration works", async () => {
    const updated = makeAlert({ explanation_source: "llm", explanation_text: "This transfer shows patterns consistent with fraud." });
    regenMock.mockResolvedValue(updated);
    const onUpdated = vi.fn();
    render(<Explanation alert={makeAlert()} onUpdated={onUpdated} />);
    fireEvent.click(screen.getByRole("button", { name: "Regenerate with AI" }));
    expect(await screen.findByText("New AI explanation written.")).toBeInTheDocument();
    expect(regenMock).toHaveBeenCalledWith(12);
    expect(onUpdated).toHaveBeenCalledWith(updated);
  });

  it("says so plainly when the AI is unavailable and the standard text stays", async () => {
    regenMock.mockResolvedValue(makeAlert());
    render(<Explanation alert={makeAlert()} onUpdated={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Regenerate with AI" }));
    expect(await screen.findByText(/AI explanation is not available right now/)).toBeInTheDocument();
  });

  it("shows an error if the request fails", async () => {
    regenMock.mockRejectedValue(new ApiError(0, "Cannot reach the server"));
    render(<Explanation alert={makeAlert()} onUpdated={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Regenerate with AI" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server");
  });

  it("disables the button while regenerating", async () => {
    let finish: (a: ReturnType<typeof makeAlert>) => void = () => {};
    regenMock.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    render(<Explanation alert={makeAlert()} onUpdated={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Regenerate with AI" }));
    expect(await screen.findByRole("button", { name: "Regenerating..." })).toBeDisabled();
    await act(async () => finish(makeAlert()));
    expect(screen.getByRole("button", { name: "Regenerate with AI" })).toBeEnabled();
  });

  it("handles a missing explanation", () => {
    render(<Explanation alert={makeAlert({ explanation_text: null })} onUpdated={() => {}} />);
    expect(screen.getByText("No explanation was stored for this alert.")).toBeInTheDocument();
  });
});
