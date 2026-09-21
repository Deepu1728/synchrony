import type { RuleFlag } from "../api/types";

export function RulesList({ rules }: { rules: RuleFlag[] }) {
  return (
    <section className="card">
      <h2>Rules that fired</h2>
      {rules.length === 0 ? (
        <p className="muted">No rules fired. The decision came from the model and the similar cases.</p>
      ) : (
        <ul className="rules">
          {rules.map((rule) => (
            <li key={rule.code}>
              <span className="rule-code mono">{rule.code}</span>
              <span>{rule.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
