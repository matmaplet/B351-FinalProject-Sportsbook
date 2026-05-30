#!/usr/bin/env bash
# One-shot fresh-data pull for a live demo.
# See REFRESH_DATA.md (Option 2) for the longer explanation.
#
# Stops on the first failure so you don't end up half-refreshed.

set -euo pipefail

cd "$(dirname "$0")"

echo "[1/5] Pulling sportsbook odds..."
python data/raw/Scripts/Sportsbooksdata.py

echo "[2/5] Pulling Kalshi markets..."
python data/raw/Scripts/kalshdata.py

echo "[3/5] Pulling Polymarket events..."
python data/raw/Scripts/polydata.py

echo "[4/5] Merging into unified snapshot..."
python data/processed/Scripts/merge.py

echo "[5/6] Re-seeding simulator off new snapshot (random seed)..."
# Random seed (not 42) so the live demo visibly differs from the
# deterministic poster version. Picks a fresh integer each run.
SIMULATE_SEED=$RANDOM python -m src.simulate

echo "[6/6] Regenerating saved plots in outputs/..."
python -m analysis.run_all

echo
echo "Done. Reload the Streamlit app (or click Regenerate simulation in"
echo "the sidebar) to pick up the new data."
