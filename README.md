# SYNCHRONY

Explainable fraud detection for payment transactions, with a console where analysts review alerts and teach the system.

## The problem
Fraud is rare (under 1% of transactions in PaySim, the public simulated dataset used here) but costly, and a fraud system fails in two directions. If it misses fraud, money is lost. If it flags too many genuine payments, customers are blocked and analysts drown in alerts. Analysts also need to know *why* a payment was flagged before they act, and the system should get better when they correct it.

SYNCHRONY scores each transaction in real time, decides approve, review or block, explains the decision, and learns from analyst verdicts.

## What it does
- **Scores** each transaction with XGBoost, rules and a similarity search over past cases (about 30 ms per request on a laptop, measured on `/score/preview`).
- **Explains** every alert with the top SHAP factors, the rules that fired, similar past cases and a plain-language summary written by Claude Haiku.
- **Learns.** When analysts confirm fraud or mark a payment genuine, that label changes how similar transactions are scored later.
- **Console.** Login, live feed colour-coded by decision, alert detail with a Confirm fraud / Mark genuine action, and a metrics page.

![Architecture](docs/architecture.svg)

More detail: [docs/architecture.md](docs/architecture.md) and [docs/phase3_adaptive_loop.md](docs/phase3_adaptive_loop.md).

```
backend/   FastAPI service, scoring, adaptive loop, simulator, red-team script, tests
ml/        Training code, trained models, metrics and reports
frontend/  React console: login, live feed, alert detail, metrics
docs/      Architecture and design notes
```

## How it decides
`score = 0.80 x XGBoost probability + 0.20 x similarity to past fraud`. A score of 0.30 or more goes to review, 0.70 or more is blocked. Two rules can force a decision regardless of the score: an amount over 10,000,000 forces review, and a transaction that closely matches analyst-confirmed fraud is forced to review (3 net cases) or block (5). The other rules (full balance drain, night hours, new receiver with a high amount) are shown to analysts as evidence and do not change the score. An Isolation Forest anomaly score is recorded for analysis only.

## Results
On the held-out PaySim test period (554,082 transactions, 4,260 fraud), XGBoost reaches 99.9% precision and 99.6% recall (4 false alarms and 19 missed fraud). Through the running system, a simulator replay of 3,275 labelled transactions flagged 91 of 91 fraud and 4 of 3,184 genuine transactions (catch rate 100%, false-positive rate 0.13%). The metrics page shows these numbers live.

**Read these with care.** PaySim is synthetic, and its fraud has a clean signature: the top SHAP feature is the balance error (`error_balance_orig`), a pattern of the simulator. Real fraud is harder. These numbers show the pipeline works end to end, not how it would perform in production. In a red-team test of evasive fraud (structuring, partial drains, daytime timing) the system missed most of the structuring and combined attacks before learning, and analyst labels recovered much of that. See [docs/phase3_adaptive_loop.md](docs/phase3_adaptive_loop.md) for the numbers and caveats.

## Setup
You need Docker, Python 3.13, Node 20+ and a free port 5432 (database), 8000 (API) and 5173 (console).

**1. Get the data and code.**
```bash
git clone <this repo> && cd SYNCHRONY
```
Download the [PaySim dataset](https://www.kaggle.com/datasets/ealaxi/paysim1) and put `PS_20174392719_1491204439457_log.csv` in `ml/data/`. The trained models are already in `ml/models/`.

**2. Configure.** Copy `.env.example` to `.env` and fill in every value.
- `JWT_SECRET` must be a long random string (32 characters or more).
- `SEED_ADMIN_PASSWORD` and `SEED_ANALYST_PASSWORD` become the passwords for the `admin` and `analyst` users. Choose strong ones.
- `ANTHROPIC_API_KEY` is optional. Without it, explanations use the built-in template.

**3. Python environment** (from the repository root).
```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

**4. Build the case features** (one time, from `ml/src`).
```bash
cd ml/src && ../../.venv/bin/python features.py && cd ../..
```

**5. Start the database.**
```bash
docker compose up -d
```

**6. Create tables, users and seed cases** (from `backend/`).
```bash
cd backend && ../.venv/bin/python -m scripts.seed
```
`scripts.seed --reset` drops every table first, which also deletes all transactions and analyst labels.

## Run
Use three terminals.

**API** (from `backend/`):
```bash
../.venv/bin/python -m uvicorn app.main:app --port 8000
```

**Console** (from `frontend/`):
```bash
npm install
npm run dev
```
Open http://localhost:5173 and log in as `admin` or `analyst`. The dev server proxies `/api` to `http://127.0.0.1:8000`; set `VITE_API_TARGET` to change that.

**Traffic** (from `backend/`):
```bash
../.venv/bin/python -m scripts.simulate --limit 300 --rate 5 --fraud-share 0.05
```
The live feed fills as transactions arrive. Open a review or block row, read the explanation, and confirm fraud or mark it genuine. The API also serves interactive docs at http://localhost:8000/docs.

The red-team experiment is `python -m scripts.redteam` (a dry run that leaves the database unchanged; see the phase 3 doc for options).

## Tests
```bash
cd backend && ../.venv/bin/python -m pytest --cov=app        # needs the database and a seeded admin user
cd frontend && npm test && npm run typecheck && npm run build
```
The backend suite has 220 tests (about 97% line coverage), including unit tests for feature engineering, each rule and the `/score` endpoint. The frontend has 100.

## Responsible AI notes
**Human in the loop.** The system flags; people decide. A review is a request for a human look, not a verdict, and the default action for uncertain cases is review rather than block. Analysts see the evidence and can overrule the system, and their verdicts are recorded with who made them and when.

**Explainability.** Every alert shows the SHAP factors behind the score, the rules that fired, the score breakdown and the most similar past cases. The text explanation is generated only from those facts.

**LLM safeguards.** The LLM only rewrites an explanation. It never makes or changes a decision. It receives derived facts only (decision, score, transaction type, amount, hour, counts, rule messages, top factors), with no account identifiers. Its output is checked before use: length limits, banned phrases, and every number it states must appear in the facts. If the check fails, the call times out, the rate limit (30 calls a minute) is reached or there is no API key, the template explanation is used. The system works fully without the LLM.

**Fairness and error costs.** A false positive delays or blocks a genuine customer. The model uses transaction and account-behaviour features only, with no personal attributes such as age, gender or location, so PaySim gives no way to test for demographic bias. A real deployment would need that testing on real data, plus a plan for customers to contest a block. Error rates should be watched over time: the metrics page reports false-positive rate and precision, and it can do so only because the simulator supplies true labels.

**Feedback can be abused or wrong.** Analyst labels change future scores. Mitigations: login required, an audit trail of every verdict, a "genuine" label that cancels a fraud label, and a minimum of 3 net confirmed cases before the learned rule fires. Roles (`admin`, `analyst`) are stored and put in the token, but no endpoint enforces them yet, so any logged-in user can submit verdicts. A compromised or careless account could bias the system, so enforcing roles, monitoring verdict counts and reviewing labels are the next steps.

**Privacy and security.** Data is account identifiers, amounts and behaviour features, with no names or contact details. Endpoints need a JWT, passwords are hashed, invalid input is rejected without being echoed back, and secrets live in `.env`, which is not committed. Real deployments would add rate limiting on login, HTTPS, secret management and data retention rules. The seed script creates accounts from passwords in `.env`, so set strong ones.

**Known limits.**
- The data is synthetic. PaySim fraud is easier to spot than real fraud, so performance here is optimistic.
- Only TRANSFER and CASH_OUT transactions are modelled, because those are the only types that contain fraud in PaySim.
- Evasive behaviour the system has not seen (for example partial drains that look like normal traffic) is caught less reliably until analysts label examples.
- The metrics page uses the simulator's true label. Live systems learn true labels late, from disputes and investigations, so live rates would be delayed and noisy.
- This is a demonstration project and has not been through model risk review or regulatory checks.
