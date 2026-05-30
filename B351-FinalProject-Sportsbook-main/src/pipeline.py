import os
import pandas as pd

from .data_loader import load_unified, devig_sportsbooks, to_wide, book_columns
from .consensus import add_consensus, deviation_table, mse_per_book
from .lead_lag import leader_scores, pairwise_lag_matrix, book_series
from .prediction import train_and_eval, build_features
from .clustering import market_state_features, fit_clusters, cluster_summary
from .anomaly import flag_anomalies, anomaly_followup
from .combined_signal import combined_score

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM_PATH = os.path.join(
    PROJECT_ROOT, "data", "processed", "csv_files", "simulated_timeseries.csv"
)


def load_wide(use_simulation=True, sport="MLB"):
    if use_simulation and os.path.exists(SIM_PATH):
        wide = pd.read_csv(SIM_PATH, parse_dates=["pulled_at"])
        if "consensus" not in wide.columns:
            wide = add_consensus(wide)
        return wide

    raw = load_unified()
    fair = devig_sportsbooks(raw)
    wide = to_wide(fair, sport=sport)
    return add_consensus(wide)


def run_all(use_simulation=True, sport="MLB"):
    wide = load_wide(use_simulation=use_simulation, sport=sport)
    books = book_columns(wide)

    out = {
        "wide": wide,
        "books": books,
        "n_rows": len(wide),
        "n_timestamps": int(wide["pulled_at"].nunique()),
    }

    out["mse_per_book"] = mse_per_book(wide)
    out["deviation_table"] = deviation_table(wide)

    out["leader_scores"] = leader_scores(wide, books)
    out["lag_matrix"] = pairwise_lag_matrix(wide, books)

    out["prediction"] = train_and_eval(wide, books)

    feats = market_state_features(wide, books)
    labelled, sil, _ = fit_clusters(feats, k=3)
    out["cluster_features"] = labelled
    out["cluster_silhouette"] = sil
    out["cluster_summary"] = cluster_summary(labelled)

    anom = flag_anomalies(wide, books)
    out["anomaly_features"] = anom
    out["anomaly_followup"] = anomaly_followup(anom)

    # feed prediction probabilities into the combined score
    proba = None
    pred = out["prediction"]
    if isinstance(pred, dict) and "logreg" in pred:
        df_full, feat_cols = build_features(wide, books)
        if not df_full.empty:
            p_up = pred["logreg"].predict_proba(df_full[feat_cols])[:, 1]
            df_full = df_full.assign(p_up=p_up)
            proba = df_full.groupby("pulled_at")["p_up"].mean()
    out["combined"] = combined_score(wide, books, prediction_proba=proba)

    return out
