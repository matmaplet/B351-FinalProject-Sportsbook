# B351 Final Project — Sportsbook / Prediction Market Behavior

We pull odds from several sportsbooks plus Kalshi and Polymarket, build a
single consensus probability, and analyze how individual books move
relative to that consensus over time.

What the project actually does (mapped to the proposal goals):

| Goal | Where it lives |
|---|---|
| C — collect odds | `data/raw/Scripts/Sportsbooksdata.py`, `kalshdata.py`, `polydata.py` |
| C — implied probabilities + de-vig | `src/probabilities.py`, `src/data_loader.py` |
| C — consensus model + plots | `src/consensus.py`, `app.py` "Overview" tab |
| B — lead-lag analysis | `src/lead_lag.py`, "Lead-Lag" tab |
| B — direction prediction (logreg + RF) | `src/prediction.py`, "Prediction" tab |
| B — clustering of market regimes | `src/clustering.py`, "Clusters" tab |
| B — evaluation metrics (MSE, accuracy, silhouette) | inside each module |
| A — anomaly detection (Isolation Forest) | `src/anomaly.py`, "Anomalies" tab |
| A — combined signal | `src/combined_signal.py`, "Combined Score" tab |
| A — dynamic updates | rerun the pullers + click "Regenerate simulation" in the app |

## How to run

1. Clone the repository.
2. Create and activate a virtual environment:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate` (Mac/Linux) or `.venv\Scripts\activate` (Windows)
3. Install dependencies:
   - `pip install -r requirements.txt`
4. (Optional) Pull fresh raw data:
   - `python data/raw/Scripts/Sportsbooksdata.py`
   - `python data/raw/Scripts/kalshdata.py`
   - `python data/raw/Scripts/polydata.py`
5. Merge into the unified file:
   - `python data/processed/Scripts/merge.py`
6. Generate a simulated time-series (used by the time-series methods):
   - `python -m src.simulate`
7. Run the full analysis once and save plots/tables to `outputs/`:
   - `python -m analysis.run_all`
8. Launch the dashboard:
   - `streamlit run app.py`

## About the simulator

The Odds API is rate-limited to one pull per minute, so the real data we
collect over a class project is just a handful of snapshots. The
simulator (`src/simulate.py`) takes the most recent real snapshot and
extends it into a per-minute time-series with a known leader book and
periodic shocks, so the lead-lag, prediction, clustering, and anomaly
modules have something to work on. The dashboard checkbox lets you
switch between simulated and real data.

## Dynamic updates

The dashboard rebuilds itself from new data without restarting:

- The "Regenerate simulation" button in the sidebar reruns
  `src/simulate.py` and writes a new `simulated_timeseries.csv`.
- `cached_run` in `app.py` keys its `@st.cache_data` on the simulated
  CSV's mtime, so the next render re-runs the full pipeline (consensus,
  lead-lag, prediction, clustering, anomaly, combined score) against
  the new file automatically.
- `./refresh_data.sh` extends this to live data: it pulls a fresh
  snapshot from all three APIs, re-merges, re-seeds the simulator with
  a random seed, and regenerates every saved plot. Reload the
  Streamlit page and every tab updates.

## Layout

```
src/                 analysis modules (one per algorithm)
analysis/run_all.py  one-shot script that produces every plot and metric
app.py               Streamlit dashboard
data/raw/            raw API pulls + puller scripts
data/processed/      merge script + unified_odds.csv + simulated_timeseries.csv
outputs/             plots saved by analysis/run_all.py
```
