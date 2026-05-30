import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score


def market_state_features(wide_with_consensus, books):
    # one row per timestamp summarising the market
    df = wide_with_consensus.copy()
    df["spread"] = df[books].max(axis=1) - df[books].min(axis=1)
    df["disagreement"] = df[books].std(axis=1)

    by_t = df.groupby("pulled_at").agg(
        mean_spread=("spread", "mean"),
        mean_disagreement=("disagreement", "mean"),
        mean_consensus=("consensus", "mean"),
    )

    by_t["consensus_change"] = by_t["mean_consensus"].diff().abs().fillna(0)
    return by_t.reset_index()


def fit_clusters(features, k=3, seed=42):
    cols = ["mean_spread", "mean_disagreement", "consensus_change"]
    X = features[cols].fillna(0.0).values
    if len(X) < k + 1:
        return features.assign(cluster=0), None, None

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    km = KMeans(n_clusters=k, n_init=10, random_state=seed)
    labels = km.fit_predict(Xs)

    sil = float(silhouette_score(Xs, labels)) if len(set(labels)) > 1 else float("nan")
    out = features.copy()
    out["cluster"] = labels
    return out, sil, km


def cluster_summary(labelled):
    return labelled.groupby("cluster").agg(
        n=("pulled_at", "count"),
        mean_spread=("mean_spread", "mean"),
        mean_disagreement=("mean_disagreement", "mean"),
        mean_change=("consensus_change", "mean"),
    )
