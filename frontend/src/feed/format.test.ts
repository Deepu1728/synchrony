import { describe, expect, it } from "vitest";
import { formatAmount, formatScore, formatTime } from "./format";

describe("feed formatting", () => {
  it("formats amounts with thousands separators and two decimals", () => {
    expect(formatAmount(1234.5)).toBe("1,234.50");
    expect(formatAmount(692654.27)).toBe("692,654.27");
    expect(formatAmount(0)).toBe("0.00");
  });

  it("formats scores to two decimals", () => {
    expect(formatScore(0.8810646)).toBe("0.88");
    expect(formatScore(0)).toBe("0.00");
  });

  it("formats times as HH:MM:SS and tolerates bad input", () => {
    expect(formatTime("2026-09-22T10:15:30+00:00")).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(formatTime("not a date")).toBe("-");
  });
});
