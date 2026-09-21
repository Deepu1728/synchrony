import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { makeAlert } from "../test/fixtures";
import { RiskScore } from "./RiskScore";

describe("RiskScore", () => {
  it("shows the combined score, decision, thresholds and every part of the breakdown", () => {
    render(<RiskScore alert={makeAlert()} />);
    expect(screen.getByTestId("combined-score")).toHaveTextContent("0.88");
    expect(screen.getByText("Block", { selector: ".badge" })).toBeInTheDocument();
    expect(screen.getByTestId("gauge-needle")).toHaveStyle({ left: "88%" });
    expect(screen.getByTestId("mark-review")).toHaveStyle({ left: "30%" });
    expect(screen.getByTestId("mark-block")).toHaveStyle({ left: "70%" });
    expect(screen.getByTestId("part-model")).toHaveTextContent("0.85");
    expect(screen.getByTestId("part-similarity")).toHaveTextContent("1.00");
    expect(screen.getByTestId("part-rules")).toHaveTextContent("0.80");
    expect(screen.getByTestId("part-anomaly")).toHaveTextContent("0.96");
    expect(screen.getByText("Model probability")).toBeInTheDocument();
    expect(screen.getByText("Similar-case share")).toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("explains when a rule, not the score, decided the outcome", () => {
    const alert = makeAlert({ decision: "block", scores: { model: 0.16, similarity: 0, anomaly: 0.5, rules: 0.5, combined: 0.13 } });
    render(<RiskScore alert={alert} />);
    expect(screen.getByRole("note")).toHaveTextContent("set by a rule");
  });

  it("keeps the needle inside the gauge for out-of-range scores", () => {
    render(<RiskScore alert={makeAlert({ scores: { model: 1, similarity: 1, anomaly: 1, rules: 1, combined: 1.4 } })} />);
    expect(screen.getByTestId("gauge-needle")).toHaveStyle({ left: "100%" });
  });
});
