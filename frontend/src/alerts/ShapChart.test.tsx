import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeAlert } from "../test/fixtures";
import { ShapChart } from "./ShapChart";

const reasons = makeAlert().reasons;

describe("ShapChart", () => {
  it("draws red bars toward fraud and blue bars toward genuine, scaled to the largest factor", () => {
    render(<ShapChart reasons={reasons} />);
    const top = screen.getByTestId("shap-error_balance_orig");
    expect(top.querySelector("[data-testid=bar-fraud]")).toHaveStyle({ width: "100%" });
    expect(top.querySelector("[data-testid=bar-genuine]")).toBeNull();

    const middle = screen.getByTestId("shap-oldbalanceOrg");
    expect(parseFloat((middle.querySelector("[data-testid=bar-fraud]") as HTMLElement).style.width)).toBeCloseTo((0.38 / 0.89) * 100, 1);

    const negative = screen.getByTestId("shap-balance_drain_ratio");
    expect(negative.querySelector("[data-testid=bar-fraud]")).toBeNull();
    expect(parseFloat((negative.querySelector("[data-testid=bar-genuine]") as HTMLElement).style.width)).toBeCloseTo((0.15 / 0.89) * 100, 1);
  });

  it("shows readable labels, values and signed numbers in the given order", () => {
    render(<ShapChart reasons={reasons} />);
    const rows = screen.getAllByTestId(/^shap-/);
    expect(rows.map((r) => r.getAttribute("data-testid"))).toEqual([
      "shap-error_balance_orig", "shap-oldbalanceOrg", "shap-balance_drain_ratio",
    ]);
    expect(screen.getByText("sender balance mismatch")).toBeInTheDocument();
    expect(screen.getByText("692,654.27")).toBeInTheDocument();
    expect(screen.getByText("+0.89")).toBeInTheDocument();
    expect(screen.getByText("−0.15")).toBeInTheDocument();
  });

  it("describes each bar for screen readers and explains the colours", () => {
    render(<ShapChart reasons={reasons} />);
    expect(screen.getByRole("img", { name: "sender balance mismatch is 0: pushes toward fraud by 0.89" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /share of sender balance sent is 1: pushes toward genuine by 0.15/ })).toBeInTheDocument();
    expect(screen.getByText(/pushes toward genuine/)).toBeInTheDocument();
    expect(screen.getByText(/pushes toward fraud/, { selector: ".legend-fraud" })).toBeInTheDocument();
  });

  it("copes with no factors and with an all-zero factor", () => {
    const { rerender } = render(<ShapChart reasons={[]} />);
    expect(screen.getByText("No factor breakdown was stored for this alert.")).toBeInTheDocument();
    rerender(<ShapChart reasons={[{ ...reasons[0], shap: 0 }]} />);
    expect(screen.getByText("0.00")).toBeInTheDocument();
  });
});
