# SYNCHRONY

Fraud detection on PaySim transactions. Each transaction is scored by XGBoost, an anomaly detector, rules and a similarity search over past cases. The result is approve, review or block, with a SHAP explanation and an LLM-written summary. Analysts confirm or reject alerts, and their labels change how similar transactions are scored later.

```
backend/   FastAPI service, scoring, adaptive loop, simulator, red-team script, tests
ml/        Training code, metrics and reports
frontend/  React console: login, live feed, alert detail, metrics
docs/      Design notes (see docs/phase3_adaptive_loop.md)
```

## Run it

You need Docker, Python 3 and Node 20+. The PaySim CSV must be in `ml/data/` to run the simulator.

**1. Configure.** Copy `.env.example` to `.env` and fill in every value. Use strong `SEED_ADMIN_PASSWORD` and `SEED_ANALYST_PASSWORD` values.

**2. Database.**
```bash
docker compose up -d
```

**3. Backend** (from `backend/`, with the virtualenv active).
```bash
python -m scripts.seed
uvicorn app.main:app --port 8000
```
`python -m scripts.seed --reset` drops every table first, so it also wipes transactions and analyst labels.

**4. Frontend** (from `frontend/`).
```bash
npm install
npm run dev
```
Open http://localhost:5173 and log in as `admin` (or the analyst user) with the seed password. The dev server proxies `/api` to `http://127.0.0.1:8000`; set `VITE_API_TARGET` to change that.

**5. Send traffic** (from `backend/`).
```bash
python -m scripts.simulate --limit 300 --rate 5 --fraud-share 0.05
```
The live feed fills as transactions arrive. Open a review or block row to see the alert, then confirm fraud or mark it genuine.

## Pages
- **Live feed:** newest transactions first, colour-coded by decision, with pause and decision filter. The list holds still while your pointer is over it.
- **Alert detail:** risk score, score breakdown, SHAP chart, explanation, rules fired, similar past cases and the Confirm fraud / Mark genuine buttons.
- **Metrics:** catch rate, false-positive rate, precision, review queue, decision counts and analyst-label counts, for 15 minutes, 1 hour, 24 hours or all time. Rates use the simulator's `true_label`, which real traffic would not have. The panel says so.

## Tests
```bash
cd backend && pytest          # needs the database running
cd frontend && npm test && npm run typecheck && npm run build
```

## Limits
PaySim is synthetic. Scores and rates here show the system works end to end, not how it would perform on real traffic. See `docs/phase3_adaptive_loop.md` for the red-team results and caveats.
