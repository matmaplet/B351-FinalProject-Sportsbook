# Generate a synthetic per-minute time-series from the latest real snapshot.
# The Odds API only allows ~1 pull per minute so we don't have enough real data
# for the time-series methods. One book is set as the leader, others follow with
# a small lag and noise. Periodic shocks add regime changes.

import os
import numpy as np
import pandas as pd

from .data_loader import load_unified, devig_sportsbooks, to_wide, book_columns

DEFAULT_OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "processed",
    "csv_files",
    "simulated_timeseries.csv",
)


def simulate(n_steps=120, step_minutes=1, leader_book=None, seed=42,
             sport="MLB", out_path=DEFAULT_OUT):
    rng = np.random.default_rng(seed)

    raw = load_unified()
    fair = devig_sportsbooks(raw)
    wide = to_wide(fair, sport=sport)

    if wide.empty:
        raise RuntimeError("no data to seed the simulator with")

    latest_t = wide["pulled_at"].max()
    seed_rows = wide[wide["pulled_at"] == latest_t].copy()

    books = book_columns(seed_rows)
    if leader_book is None or leader_book not in books:
        leader_book = books[0]

    out_rows = []
    state = {}
    for _, r in seed_rows.iterrows():
        key = (r["game_id"], r["team"])
        state[key] = {b: r[b] for b in books}

    truth = {k: np.nan for k in state}
    for k in truth:
        v = state[k].get(leader_book)
        truth[k] = v if pd.notna(v) else 0.5

    pending = {k: [] for k in state}  # leader history followers chase

    shock_steps = set(range(20, n_steps, 25))

    for step in range(n_steps):
        t = latest_t + pd.Timedelta(minutes=step_minutes * (step + 1))
        is_shock = step in shock_steps

        for key, books_state in state.items():
            jump = rng.normal(0, 0.05) if is_shock else rng.normal(0, 0.005)
            truth[key] = float(np.clip(truth[key] + jump, 0.02, 0.98))

            # leader moves toward truth quickly
            lead = books_state[leader_book]
            if pd.isna(lead):
                lead = truth[key]
            lead = float(np.clip(lead + 0.6 * (truth[key] - lead) +
                                 rng.normal(0, 0.004), 0.01, 0.99))
            books_state[leader_book] = lead
            pending[key].append(lead)

            # followers chase the leader with a 1-2 step lag
            for b in books:
                if b == leader_book:
                    continue
                target_idx = max(0, len(pending[key]) - rng.integers(1, 3))
                target = pending[key][target_idx]
                cur = books_state[b]
                if pd.isna(cur):
                    cur = target
                noise = rng.normal(0, 0.02 if is_shock else 0.006)
                cur = float(np.clip(cur + 0.4 * (target - cur) + noise, 0.01, 0.99))
                books_state[b] = cur

            row = {"pulled_at": t, "game_id": key[0], "team": key[1]}
            row.update(books_state)
            out_rows.append(row)

    sim = pd.DataFrame(out_rows)
    full = sim.sort_values(["game_id", "team", "pulled_at"]).reset_index(drop=True)
    full["consensus"] = full[books].mean(axis=1, skipna=True)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    full.to_csv(out_path, index=False)
    print(f"simulated {len(full)} rows ({n_steps} synthetic steps) -> {out_path}")
    print(f"leader book: {leader_book}")
    return full


if __name__ == "__main__":
    # Override the seed and sport via env vars.
    # `python -m src.simulate`                                -> seed=42, MLB
    # `SIMULATE_SEED=$RANDOM python -m src.simulate`          -> fresh random walk
    # `SIMULATE_SPORT=NBA python -m src.simulate`             -> NBA instead of MLB
    env_seed = os.environ.get("SIMULATE_SEED")
    seed = int(env_seed) if env_seed else 42
    sport = os.environ.get("SIMULATE_SPORT", "MLB")
    simulate(seed=seed, sport=sport)
