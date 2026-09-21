import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { makeSimilar } from "../test/fixtures";
import { SimilarCases } from "./SimilarCases";

const renderCases = (similar: Parameters<typeof SimilarCases>[0]["similar"], onRetry = vi.fn()) =>
  render(<MemoryRouter><SimilarCases similar={similar} onRetry={onRetry} /></MemoryRouter>);

describe("SimilarCases", () => {
  it("summarises the neighbours and lists each case", () => {
    renderCases({ status: "ready", data: makeSimilar() });
    expect(screen.getByTestId("similar-summary")).toHaveTextContent("2 of 3 of the most similar past cases were fraud");
    expect(screen.getByTestId("similar-summary")).toHaveTextContent("1 confirmed fraud and 0 marked genuine by analysts");

    const fraudCase = screen.getByTestId("case-1");
    expect(fraudCase).toHaveClass("row-block");
    expect(fraudCase).toHaveTextContent("Fraud");
    expect(fraudCase).toHaveTextContent("Training data");
    expect(fraudCase).toHaveTextContent("Transfer");
    expect(fraudCase).toHaveTextContent("640,000.50");
    expect(fraudCase).toHaveTextContent("04");
    expect(fraudCase).toHaveTextContent("0.01");

    const legit = screen.getByTestId("case-3");
    expect(legit).toHaveClass("row-approve");
    expect(legit).toHaveTextContent("Genuine");
    expect(legit.textContent).toContain("-");
  });

  it("links analyst-labelled cases to their alerts", () => {
    renderCases({ status: "ready", data: makeSimilar() });
    const link = screen.getByRole("link", { name: "alert 77" });
    expect(link).toHaveAttribute("href", "/alerts/77");
    expect(screen.getByTestId("case-2")).toHaveTextContent("Analyst review");
  });

  it("leaves out the analyst sentence when no analyst labels are involved", () => {
    renderCases({ status: "ready", data: makeSimilar({ summary: { fraud: 2, legit: 1, learned_fraud: 0, learned_legit: 0 } }) });
    expect(screen.getByTestId("similar-summary")).not.toHaveTextContent("analysts");
  });

  it("shows loading, error with retry, and empty states", () => {
    const onRetry = vi.fn();
    const { rerender } = renderCases({ status: "loading" }, onRetry);
    expect(screen.getByText("Looking up similar cases...")).toBeInTheDocument();

    rerender(<MemoryRouter><SimilarCases similar={{ status: "error", message: "boom", notFound: false }} onRetry={onRetry} /></MemoryRouter>);
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load similar cases: boom");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);

    rerender(<MemoryRouter><SimilarCases similar={{ status: "ready", data: makeSimilar({ cases: [] }) }} onRetry={onRetry} /></MemoryRouter>);
    expect(screen.getByText("No similar cases were found.")).toBeInTheDocument();
  });
});
