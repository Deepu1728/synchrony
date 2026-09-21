import type { KeyboardEvent } from "react";
import type { FeedRow } from "../api/types";
import { ALERT_STATUS_LABEL, DECISION_LABEL, formatAmount, formatScore, formatTime, TYPE_LABEL } from "./format";

type Props = {
  rows: FeedRow[];
  onOpen: (alertId: number) => void;
};

function truthLabel(label: boolean | null): string {
  if (label === null) return "-";
  return label ? "fraud" : "genuine";
}

export function FeedTable({ rows, onOpen }: Props) {
  return (
    <div className="table-wrap">
      <table className="feed-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>Type</th>
            <th className="num">Amount</th>
            <th>From / To</th>
            <th>Score</th>
            <th>Decision</th>
            <th>Alert</th>
            <th>Simulator label</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const clickable = row.alert_id !== null;
            const open = () => clickable && onOpen(row.alert_id as number);
            const onKey = (event: KeyboardEvent) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                open();
              }
            };
            return (
              <tr
                key={row.id}
                className={`row row-${row.decision}${clickable ? " row-clickable" : ""}`}
                onClick={clickable ? open : undefined}
                onKeyDown={clickable ? onKey : undefined}
                tabIndex={clickable ? 0 : undefined}
                aria-label={clickable ? `${DECISION_LABEL[row.decision]} transaction, open alert ${row.alert_id}` : undefined}
                data-testid={`row-${row.id}`}
              >
                <td className="mono">{formatTime(row.created_at)}</td>
                <td>{TYPE_LABEL[row.type] ?? row.type}</td>
                <td className="num mono">{formatAmount(row.amount)}</td>
                <td className="mono muted">{row.name_orig} &rarr; {row.name_dest}</td>
                <td>
                  <span className="score">
                    <span className="score-bar" aria-hidden="true">
                      <span className={`score-fill fill-${row.decision}`} style={{ width: `${Math.min(row.score, 1) * 100}%` }} />
                    </span>
                    <span className="mono">{formatScore(row.score)}</span>
                  </span>
                </td>
                <td><span className={`badge badge-${row.decision}`}>{DECISION_LABEL[row.decision]}</span></td>
                <td>
                  {row.alert_status ? (
                    <span className={`tag tag-${row.alert_status}`}>{ALERT_STATUS_LABEL[row.alert_status]}</span>
                  ) : (
                    <span className="muted">-</span>
                  )}
                </td>
                <td className="muted">{truthLabel(row.true_label)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
