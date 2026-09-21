import type { TransactionDetail } from "../api/types";
import { formatAmount, TYPE_LABEL } from "../feed/format";
import { formatDateTime } from "./format";

export function TransactionCard({ transaction: t }: { transaction: TransactionDetail }) {
  const rows: [string, string][] = [
    ["Type", TYPE_LABEL[t.type] ?? t.type],
    ["Amount", formatAmount(t.amount)],
    ["From", t.name_orig],
    ["To", t.name_dest],
    ["Sender balance", `${formatAmount(t.oldbalance_org)} → ${formatAmount(t.newbalance_orig)}`],
    ["Receiver balance", `${formatAmount(t.oldbalance_dest)} → ${formatAmount(t.newbalance_dest)}`],
    ["Hour of day", String(t.step % 24).padStart(2, "0")],
    ["Received", formatDateTime(t.created_at)],
  ];
  if (t.true_label !== null) rows.push(["Simulator label", t.true_label ? "fraud" : "genuine"]);
  return (
    <section className="card">
      <h2>Transaction</h2>
      <dl className="facts">
        {rows.map(([label, value]) => (
          <div key={label} className="fact"><dt>{label}</dt><dd className="mono">{value}</dd></div>
        ))}
      </dl>
    </section>
  );
}
