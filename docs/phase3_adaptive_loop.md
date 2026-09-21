# Phase 3: Adaptive loop

## What it does
Analysts' labels change how the system scores similar transactions in the future.

- `POST /feedback` (alert reviewed) and `POST /transactions/{id}/report-fraud` (fraud that was approved, for example a customer dispute) both store the transaction as a labelled case.
- Rule `LEARNED_FRAUD_PATTERN`: among the 10 most similar cases, analyst-confirmed fraud minus analyst-confirmed legitimate is 3 or more sends a transaction to review, and 5 or more blocks it. Seeded training cases never count, only analyst labels.
- A "legitimate" label cancels one fraud label, so false alarms can be cleared by analysts.
- Case search is exact (not approximate), so results are identical on every database.

## Red-team experiment
`backend/scripts/redteam.py` rewrites real held-out fraud into evasive variants, changing only what an attacker controls: split into transfers just under the 200k rule threshold (structuring), take part of the balance (partial drain), move to daytime hours, first deposit small normal-looking amounts into the receiving account (groomed mule), and a combination. Balances stay consistent and every attack uses fresh accounts.

Protocol: score 60 fresh attacks (before), analysts label 20 attacks, score 60 different fresh attacks (after). Genuine transactions (3,000) are re-scored read-only on the same rows before and after.

| Variant | Fraud flagged | Blocked | Stolen money that got through | Genuine flagged (of 3,000) |
|---|---|---|---|---|
| Structuring | 9.0% -> 77.4% | 7.0% -> 64.2% | 87.3% -> 17.2% | 2 -> 11 |
| Combo | 16.7% -> 71.7% | 0% -> 55.0% | 27.0% -> 2.7% | 2 -> 2 |
| Partial drain | 41.7% -> 56.7% | 16.7% -> 31.7% | 45.4% -> 24.0% | 2 -> 3 |
| Groomed mule (control) | 100% -> 100% | 95% -> 100% | 0% -> 0% | 2 -> 2 |

Chart: `ml/reports/11_redteam_before_after.png`. Raw numbers: `ml/metrics/redteam_results.json`.

## Honest caveats
- PaySim is synthetic and the variants are ones we designed. This is a robustness stress test, not a proof of real-world performance.
- Partial drain is the weakest case: a single mid-size transfer looks like normal traffic.
- Learning costs a few extra reviews (structuring: 9 more per 3,000 genuine, review only). Marking those legitimate switches the rule off for similar transactions again (measured on held-out data: 9 extra flags fell back to 2 after clearing about 5 alerts).
- Numbers move by a few points between run sizes (a 40-attack run gave structuring 84% -> 7% of money through; the 60-attack run gives 87% -> 17%).
- Feedback can be abused by someone with analyst access. Mitigations: roles, an audit trail in the feedback table, and the 3-case minimum.
- Approximate nearest-neighbour search (HNSW) returned different neighbours on different index builds, which made the first version of this experiment irreproducible. Search is now exact (about 5 ms per query at 23k cases); switch back with `SIMILARITY_EXACT=false` only for very large case stores.

## Reproduce
```bash
cd backend
../.venv/bin/python -m scripts.redteam --show            # one example of each variant
../.venv/bin/python -m scripts.redteam --scenarios 60 --learn 20 --genuine 3000 \
  --report ../ml/metrics/redteam_results.json --plot ../ml/reports/11_redteam_before_after.png
```

The default is a dry run that is rolled back, so the database is left unchanged.