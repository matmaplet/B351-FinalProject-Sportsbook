# Demo modes

There are two ways to run the dashboard for a presentation. Both use
the same pipeline; the only difference is whether the underlying data
snapshot is fresh or frozen.

---

## Option 1 — Deterministic demo (default, recommended for poster)

**What it does:** uses whatever `simulated_timeseries.csv` is currently
on disk, with the simulator's seed fixed at `42`
([`src/simulate.py`](src/simulate.py)). Every run produces
byte-for-byte identical output, so the numbers on screen always match
the numbers on the poster.

**When to use it:** during the actual presentation, or any time you
want reproducibility.

**How to run it:**

```bash
streamlit run app.py
```

That's it. **Don't run `refresh_data.sh` first** — that's Option 2 and
will overwrite the deterministic CSV. Clicking "Regenerate simulation"
in the sidebar is also safe: it re-runs the simulator with seed=42,
which reproduces the same file.

**To verify determinism:** run `python -m src.simulate` twice and
compare `data/processed/csv_files/simulated_timeseries.csv` — the files
will be identical.

> **Heads-up.** If you've already run `./refresh_data.sh` once, the
> seed=42 file from your poster session is gone — re-running
> `python -m src.simulate` reproduces seed=42 against the *new* raw
> snapshot, which is close but not identical to the poster numbers. To
> guarantee you can roll back, copy the file before refreshing:
> `cp data/processed/csv_files/simulated_timeseries.csv data/processed/csv_files/baseline.csv`
> and copy it back when you want the poster version.

---

## Option 2 — Fresh real-data pull (live mode)

**What it does:** pulls new odds from the Odds API, Kalshi, and
Polymarket; merges them; re-seeds the simulator off the new snapshot
**with a random seed**; then regenerates every saved plot in
`outputs/`. Both the input data and the RNG change, so the dashboard
visibly differs from the poster — different teams in the dropdown,
different MSE numbers, different lead-lag heatmap.

**When to use it:** if a reviewer asks "can it produce different
results?" or "is this on live data?" Run this once, then reload the
dashboard.

### One-time setup: API key

Only the Odds API needs a key. Kalshi and Polymarket are public.

1. Get a free key from https://the-odds-api.com/ (500 reqs/month free).
2. Copy the template and fill in your key:
   ```bash
   cp .env.example .env
   # edit .env, replace your_key_here with the real key
   ```
3. `.env` is gitignored. `.env.example` is committed as the template.
   The puller loads `.env` automatically via `python-dotenv`.

If you'd rather not use a `.env` file:

```bash
export ODDS_API_KEY=your_key_here
```

If the variable is missing the puller exits with a clear error
instead of running keyless.

### Running the refresh

One command:

```bash
./refresh_data.sh
```

That script runs all six steps in order and stops on the first
failure:

1. `python data/raw/Scripts/Sportsbooksdata.py` — fresh sportsbook odds
2. `python data/raw/Scripts/kalshdata.py` — fresh Kalshi markets
3. `python data/raw/Scripts/polydata.py` — fresh Polymarket events
4. `python data/processed/Scripts/merge.py` — unify into one snapshot
5. `SIMULATE_SEED=$RANDOM python -m src.simulate` — re-seed simulator
   with a fresh random seed
6. `python -m analysis.run_all` — regenerate every PNG in `outputs/`

Then either start `streamlit run app.py`, or — if it's already running —
just reload the page (Cmd+R). The dashboard auto-detects the new CSV
and rebuilds every plot.

### Caveats

- **Rate limit.** Odds API allows ~1 pull/minute. Don't spam during a
  live demo.
- **Off-season.** If no MLB or NBA games are scheduled when you pull,
  the unified snapshot will be empty and `python -m src.simulate` will
  refuse to run. Check that `data/processed/csv_files/unified_odds.csv`
  has rows before re-simulating.
- **Don't commit `.env`.** It's gitignored, but glance at `git status`
  before pushing.

---

## Rollback

If a live pull fails mid-demo, do nothing — the existing
`simulated_timeseries.csv` is still on disk and the dashboard keeps
showing the previous (deterministic) results. Only re-running
`python -m src.simulate` would overwrite it.
