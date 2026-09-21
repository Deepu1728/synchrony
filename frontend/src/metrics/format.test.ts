import { describe, expect, it } from "vitest";
import { formatCount, formatPercent, share } from "./format";

describe("metrics format", () => {
  it("formats percentages", () => {
    expect(formatPercent(null)).toBe("-");
    expect(formatPercent(0)).toBe("0%");
    expect(formatPercent(1)).toBe("100%");
    expect(formatPercent(0.0013)).toBe("0.13%");
    expect(formatPercent(0.9579)).toBe("95.8%");
    expect(formatPercent(0.00001)).toBe("<0.01%");
  });
  it("never rounds up to 100% when not perfect", () => {
    expect(formatPercent(0.99996)).toBe("99.9%");
  });
  it("formats counts and shares", () => {
    expect(formatCount(3184)).toBe("3,184");
    expect(share(1, 4)).toBe(0.25);
    expect(share(1, 0)).toBe(0);
  });
});
