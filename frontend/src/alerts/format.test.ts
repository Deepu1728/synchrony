import { describe, expect, it } from "vitest";
import { decisionFromScore, formatDateTime, formatFeatureValue, formatSigned, sourceLabel } from "./format";

describe("alert formatting", () => {
  it("formats feature values", () => {
    expect(formatFeatureValue(0)).toBe("0");
    expect(formatFeatureValue(1)).toBe("1");
    expect(formatFeatureValue(692654.27)).toBe("692,654.27");
    expect(formatFeatureValue(2.4336)).toBe("2.43");
    expect(formatFeatureValue(1500000)).toBe("1,500,000");
  });

  it("formats signed contributions with a proper minus sign", () => {
    expect(formatSigned(0.891)).toBe("+0.89");
    expect(formatSigned(-0.149)).toBe("−0.15");
    expect(formatSigned(0)).toBe("0.00");
    expect(formatSigned(0.001)).toBe("0.00");
  });

  it("labels case sources and falls back to the raw value", () => {
    expect(sourceLabel("paysim_train")).toBe("Training data");
    expect(sourceLabel("feedback")).toBe("Analyst review");
    expect(sourceLabel("reported")).toBe("Customer report");
    expect(sourceLabel("something_new")).toBe("something_new");
  });

  it("derives the decision a score alone would give", () => {
    expect(decisionFromScore(0.1, 0.3, 0.7)).toBe("approve");
    expect(decisionFromScore(0.3, 0.3, 0.7)).toBe("review");
    expect(decisionFromScore(0.7, 0.3, 0.7)).toBe("block");
  });

  it("formats date and time and tolerates bad input", () => {
    expect(formatDateTime("2026-09-22T10:15:30+00:00")).toMatch(/2026/);
    expect(formatDateTime("nope")).toBe("-");
  });
});
