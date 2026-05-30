import numpy as np
import pandas as pd

from .clustering import market_state_features
from .anomaly import flag_anomalies


def _minmax(x):
    x = np.asarray(x, dtype=float)
    if not np.isfinite(x).any():
        return np.zeros_like(x)
    lo, hi = np.nanmin(x), np.nanmax(x)
    if hi - lo < 1e-12:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def combined_score(wide_with_consensus, books,
                   weights=None, prediction_proba=None):
    if weights is None:
        weights = {"disagreement": 0.25, "movement": 0.25,
                   "anomaly": 0.25, "prediction": 0.25}

    feats = flag_anomalies(wide_with_consensus, books)
    feats = feats.sort_values("pulled_at").reset_index(drop=True)

    feats["disagreement_score"] = _minmax(feats["mean_disagreement"])
    feats["movement_score"] = _minmax(feats["consensus_change"])
    feats["anomaly_score"] = 1.0 - _minmax(feats["score"])

    if prediction_proba is not None:
        p = prediction_proba.reindex(feats["pulled_at"]).fillna(0.5).values
        feats["prediction_score"] = _minmax(np.abs(p - 0.5))
    else:
        feats["prediction_score"] = 0.0

    feats["combined"] = (
        weights["disagreement"] * feats["disagreement_score"]
        + weights["movement"] * feats["movement_score"]
        + weights["anomaly"] * feats["anomaly_score"]
        + weights["prediction"] * feats["prediction_score"]
    )
    return feats
