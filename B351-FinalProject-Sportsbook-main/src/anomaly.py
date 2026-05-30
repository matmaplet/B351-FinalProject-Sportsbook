import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from .clustering import market_state_features


def flag_anomalies(wide_with_consensus, books, contamination=0.1, seed=42):
    feats = market_state_features(wide_with_consensus, books)
    cols = ["mean_spread", "mean_disagreement", "consensus_change"]
    X = feats[cols].fillna(0.0).values
    if len(X) < 10:
        feats["is_anomaly"] = 0
        feats["score"] = 0.0
        return feats

    iso = IsolationForest(contamination=contamination, random_state=seed)
    labels = iso.fit_predict(X)        # -1 anomaly, 1 normal
    scores = iso.score_samples(X)

    feats = feats.copy()
    feats["is_anomaly"] = (labels == -1).astype(int)
    feats["score"] = scores
    return feats


def anomaly_followup(feats, lookahead=1):
    # check if anomalies are followed by bigger consensus moves
    feats = feats.sort_values("pulled_at").reset_index(drop=True)
    feats["next_change"] = (
        feats["mean_consensus"].shift(-lookahead) - feats["mean_consensus"]
    ).abs()

    on = feats.loc[feats["is_anomaly"] == 1, "next_change"].dropna()
    off = feats.loc[feats["is_anomaly"] == 0, "next_change"].dropna()

    return {
        "n_anomaly": int(len(on)),
        "n_normal": int(len(off)),
        "mean_move_after_anomaly": float(on.mean()) if len(on) else float("nan"),
        "mean_move_after_normal": float(off.mean()) if len(off) else float("nan"),
    }
