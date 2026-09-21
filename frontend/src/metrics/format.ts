export function formatPercent(value: number | null): string {
  if (value === null) return "-";
  const percent = value * 100;
  if (percent === 0) return "0%";
  if (percent < 0.01) return "<0.01%";
  const text = percent.toFixed(percent < 1 ? 2 : 1);
  if (percent < 100 && Number(text) >= 100) return "99.9%";
  return `${text.replace(/\.0+$/, "")}%`;
}

export const formatCount = (value: number): string => value.toLocaleString("en-US");

export const share = (part: number, total: number): number => (total === 0 ? 0 : part / total);
