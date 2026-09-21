import type { ReactNode } from "react";

type Props = {
  title: string;
  help: string;
  value: string;
  detail: ReactNode;
  extra?: ReactNode;
  testId: string;
};

export function MetricCard({ title, help, value, detail, extra, testId }: Props) {
  return (
    <section className="card metric" data-testid={testId}>
      <h2>{title}</h2>
      <p className="muted small metric-help">{help}</p>
      <p className="metric-value" data-testid={`${testId}-value`}>{value}</p>
      <p className="metric-detail">{detail}</p>
      {extra && <p className="muted small">{extra}</p>}
    </section>
  );
}
