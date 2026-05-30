import os
import pandas as pd

from .probabilities import remove_margin_pair

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIFIED_CSV = os.path.join(
    PROJECT_ROOT, "data", "processed", "csv_files", "unified_odds.csv"
)


def _make_game_id(home, away):
    # Sort the two team names so the matchup is identified the same way
    # regardless of which source called which side "home". Without this,
    # Sportsbook ("Boston vs Toronto") and Kalshi ("Toronto vs Boston")
    # for the same game become two separate game_ids and never merge.
    h = (home or "").strip()
    a = (away or "").strip()
    if not h and not a:
        return ""
    if not h:
        return a
    if not a:
        return h
    lo, hi = sorted([h, a])
    return f"{lo} vs {hi}"


def load_unified(path=UNIFIED_CSV):
    df = pd.read_csv(path)
    df["pulled_at"] = pd.to_datetime(df["pulled_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["pulled_at", "implied_prob", "team"])
    df["game_id"] = [
        _make_game_id(h, a)
        for h, a in zip(df["home_team"].fillna(""), df["away_team"].fillna(""))
    ]
    return df


def devig_sportsbooks(df):
    # only sportsbook rows have a 2-sided market we can de-vig
    sb = df[df["source"] == "odds"].copy()
    other = df[df["source"] != "odds"].copy()

    fixed_rows = []
    keys = ["pulled_at", "source_event_id", "bookmaker"]
    for _, group in sb.groupby(keys):
        if len(group) != 2:
            continue
        a, b = group.iloc[0], group.iloc[1]
        pa, pb = remove_margin_pair(a["implied_prob"], b["implied_prob"])
        if pa is None:
            continue
        ra = a.copy()
        rb = b.copy()
        ra["implied_prob"] = pa
        rb["implied_prob"] = pb
        fixed_rows.append(ra)
        fixed_rows.append(rb)

    if fixed_rows:
        sb_fixed = pd.DataFrame(fixed_rows)
    else:
        sb_fixed = sb.iloc[0:0].copy()

    return pd.concat([sb_fixed, other], ignore_index=True)


def to_wide(df, sport=None):
    # row per (time, game, team), column per book
    if sport is not None:
        df = df[df["sport"] == sport]
    cols = ["pulled_at", "game_id", "team", "bookmaker", "implied_prob"]
    df = df[cols].drop_duplicates()
    wide = df.pivot_table(
        index=["pulled_at", "game_id", "team"],
        columns="bookmaker",
        values="implied_prob",
        aggfunc="mean",
    )
    return wide.reset_index()


def book_columns(wide):
    skip = {"pulled_at", "game_id", "team", "consensus"}
    return [c for c in wide.columns if c not in skip]
