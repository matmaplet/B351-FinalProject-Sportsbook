# Streamlit dashboard. Run with: streamlit run app.py

import os
import sys

import altair as alt
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import run_all, load_wide, SIM_PATH
from src.simulate import simulate

st.set_page_config(page_title="Sportsbook Behavior", layout="wide")
st.title("Sportsbook / Prediction Market Behavior")
st.caption("B351 final project — consensus, lead-lag, prediction, clusters, anomalies.")


# sidebar
st.sidebar.header("Data")
use_sim = st.sidebar.checkbox(
    "Use simulated time-series",
    value=True,
    help="Real polls are sparse (1 per minute API limit). Simulator extends the "
         "latest snapshot with a random walk.",
)

if st.sidebar.button("Regenerate simulation"):
    with st.spinner("Simulating..."):
        simulate()
    st.sidebar.success("Done. Reload the page.")

if use_sim and not os.path.exists(SIM_PATH):
    st.sidebar.warning("No simulated file yet. Click 'Regenerate simulation'.")
    st.stop()


@st.cache_data(show_spinner=True)
def cached_run(use_sim_flag, sport, sim_mtime):
    # sim_mtime is part of the cache key so that when the simulated CSV is
    # rewritten (Regenerate button or refresh_data.sh), the cache invalidates.
    return run_all(use_simulation=use_sim_flag, sport=sport)


# The simulator file is built off a single sport at generation time.
# To switch sports, re-run `SIMULATE_SPORT=NBA python -m src.simulate`.
sport = "MLB"
sim_mtime = os.path.getmtime(SIM_PATH) if os.path.exists(SIM_PATH) else 0.0
res = cached_run(use_sim, sport, sim_mtime)

wide = res["wide"]
books = res["books"]


# top-line stats
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", res["n_rows"])
c2.metric("Timestamps", res["n_timestamps"])
c3.metric("Books", len(books))
c4.metric(
    "Best book (lowest MSE)",
    res["mse_per_book"].index[0] if not res["mse_per_book"].empty else "—",
)

tabs = st.tabs(
    ["Overview", "Lead-Lag", "Prediction", "Clusters", "Anomalies", "Combined Score"]
)


# Overview
with tabs[0]:
    st.subheader("Implied probability over time")
    st.caption(
        "Each line is one bookmaker's implied probability that the "
        "selected team wins this specific game, over time. The black "
        "line is the consensus (mean across books)."
    )
    pairs = wide[["game_id", "team"]].drop_duplicates().reset_index(drop=True)
    pair_idx = st.selectbox(
        "Pick a game and a side to back",
        pairs.index,
        format_func=lambda i: (
            f"{pairs.loc[i, 'game_id']} — backing {pairs.loc[i, 'team']}"
            if pairs.loc[i, "game_id"]
            else f"{pairs.loc[i, 'team']} (no matchup info)"
        ),
    )
    sub = wide[
        (wide["game_id"] == pairs.loc[pair_idx, "game_id"])
        & (wide["team"] == pairs.loc[pair_idx, "team"])
    ].sort_values("pulled_at")

    fig, ax = plt.subplots(figsize=(10, 4))
    for b in books:
        ax.plot(sub["pulled_at"], sub[b], label=b, alpha=0.7)
    ax.plot(
        sub["pulled_at"], sub["consensus"], label="consensus",
        color="black", linewidth=2,
    )
    ax.set_xlabel("time")
    ax.set_ylabel("implied probability")
    ax.legend(loc="best", fontsize=8)
    st.pyplot(fig)

    st.subheader("MSE of each book vs the consensus")
    st.bar_chart(res["mse_per_book"])

    st.subheader("Deviation distribution")
    devs = res["deviation_table"]
    if not devs.empty:
        fig, ax = plt.subplots(figsize=(10, 4))
        sns.boxplot(data=devs, x="book", y="deviation", ax=ax)
        ax.axhline(0, color="black", linewidth=0.8)
        plt.xticks(rotation=30, ha="right")
        st.pyplot(fig)


# Lead-Lag
with tabs[1]:
    st.subheader("Leader scores")
    st.caption(
        "Each value = average best lag of this book against every other book. "
        "Positive means this book moves first."
    )
    st.bar_chart(res["leader_scores"])

    st.subheader("Pairwise lag matrix")
    mat = res["lag_matrix"].astype(float)
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.heatmap(mat, annot=True, cmap="vlag", center=0, ax=ax)
    ax.set_title("Best lag of row vs col (positive = row leads col)")
    st.pyplot(fig)


# Prediction
with tabs[2]:
    pred = res["prediction"]
    if "error" in pred:
        st.warning(pred["error"])
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Logistic regression", f"{pred['logreg_accuracy']:.3f}")
        c2.metric("Random forest", f"{pred['rf_accuracy']:.3f}")
        c3.metric("Baseline (majority)", f"{pred['baseline_accuracy']:.3f}")

        st.subheader("Random forest feature importance")
        st.bar_chart(pred["feature_importance"])

        st.caption(
            f"Trained on {pred['n_train']} rows, tested on {pred['n_test']} "
            "(time-ordered split)."
        )


# Clusters
with tabs[3]:
    st.subheader("Market regimes")
    st.caption(
        "K-means on (mean spread, mean disagreement, consensus change). "
        f"Silhouette: {res['cluster_silhouette']:.3f}"
        if res["cluster_silhouette"] is not None
        else "Silhouette: n/a"
    )

    cf = res["cluster_features"].copy()

    # Distance from each point to its cluster centroid — used both to
    # call out outliers and to highlight them on the scatter.
    feat_cols = ["mean_spread", "mean_disagreement", "consensus_change"]
    centroids = cf.groupby("cluster")[feat_cols].transform("mean")
    diffs = cf[feat_cols] - centroids
    cf["dist_to_centroid"] = (diffs ** 2).sum(axis=1) ** 0.5

    # Top 3 furthest-from-centroid points per cluster = outliers.
    outliers = (
        cf.sort_values("dist_to_centroid", ascending=False)
          .groupby("cluster")
          .head(3)
    )
    cf["is_outlier"] = cf["pulled_at"].isin(outliers["pulled_at"])

    base = alt.Chart(cf).encode(
        x=alt.X("mean_disagreement:Q", title="Mean disagreement"),
        y=alt.Y("consensus_change:Q", title="Consensus change"),
        color=alt.Color("cluster:N", legend=alt.Legend(title="Cluster")),
        tooltip=[
            alt.Tooltip("pulled_at:T", title="Time"),
            alt.Tooltip("cluster:N"),
            alt.Tooltip("mean_spread:Q", format=".4f"),
            alt.Tooltip("mean_disagreement:Q", format=".4f"),
            alt.Tooltip("consensus_change:Q", format=".4f"),
            alt.Tooltip("dist_to_centroid:Q", format=".4f"),
        ],
    )
    points = base.mark_circle(size=80, opacity=0.7)
    outlier_ring = (
        base.transform_filter("datum.is_outlier")
            .mark_point(size=180, stroke="red", strokeWidth=2, filled=False)
    )
    st.altair_chart(
        (points + outlier_ring).interactive(),
        use_container_width=True,
    )
    st.caption(
        "Hover any point for its timestamp and feature values. "
        "Red rings mark the 3 furthest-from-centroid points per cluster — "
        "the points that least fit their assigned regime."
    )

    st.write("Outliers (top 3 furthest from each cluster's centroid):")
    st.dataframe(
        outliers[["pulled_at", "cluster", "mean_disagreement",
                  "consensus_change", "dist_to_centroid"]]
        .sort_values(["cluster", "dist_to_centroid"], ascending=[True, False])
        .reset_index(drop=True)
    )

    st.write("Per-cluster summary:")
    st.dataframe(res["cluster_summary"])


# Anomalies
with tabs[4]:
    af = res["anomaly_features"]
    fu = res["anomaly_followup"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Anomaly timestamps", fu["n_anomaly"])
    c2.metric("Mean next move (anomaly)", f"{fu['mean_move_after_anomaly']:.4f}")
    c3.metric("Mean next move (normal)", f"{fu['mean_move_after_normal']:.4f}")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(af["pulled_at"], af["mean_consensus"], color="steelblue",
            label="mean consensus")
    flagged = af[af["is_anomaly"] == 1]
    ax.scatter(flagged["pulled_at"], flagged["mean_consensus"],
               color="red", label="anomaly", zorder=5)
    ax.legend()
    st.pyplot(fig)


# Combined score
with tabs[5]:
    st.subheader("Combined market-attention score")
    st.caption(
        "Weighted mix of (book disagreement) + (consensus movement) + "
        "(anomaly weirdness) + (model confidence). Tune weights below."
    )

    w_dis = st.slider("Disagreement weight", 0.0, 1.0, 0.25, 0.05)
    w_mov = st.slider("Movement weight", 0.0, 1.0, 0.25, 0.05)
    w_ano = st.slider("Anomaly weight", 0.0, 1.0, 0.25, 0.05)
    w_pre = st.slider("Prediction weight", 0.0, 1.0, 0.25, 0.05)

    cs = res["combined"].copy()
    total = w_dis + w_mov + w_ano + w_pre or 1.0
    cs["combined"] = (
        w_dis / total * cs["disagreement_score"]
        + w_mov / total * cs["movement_score"]
        + w_ano / total * cs["anomaly_score"]
        + w_pre / total * cs["prediction_score"]
    )

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(cs["pulled_at"], cs["combined"], color="darkorange")
    ax.set_ylabel("score (0..1)")
    st.pyplot(fig)

    st.dataframe(
        cs[["pulled_at", "disagreement_score", "movement_score",
            "anomaly_score", "prediction_score", "combined"]]
        .sort_values("combined", ascending=False)
        .head(10)
    )
