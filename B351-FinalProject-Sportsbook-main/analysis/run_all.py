# Run the full pipeline once and dump plots + tables to outputs/.
# Usage: python -m analysis.run_all

import os
import sys
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulate import simulate
from src.pipeline import run_all, SIM_PATH

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs"
)


def save_plot(fig, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, bbox_inches="tight", dpi=120)
    plt.close(fig)
    print("saved", path)


def main():
    if not os.path.exists(SIM_PATH):
        print("simulated time-series not found, generating one...")
        simulate()

    res = run_all(use_simulation=True)
    wide = res["wide"]
    books = res["books"]

    print("\n=== Dataset ===")
    print("rows:", res["n_rows"])
    print("timestamps:", res["n_timestamps"])
    print("books:", books)

    # consensus over time for one game/team
    sample_key = wide[["game_id", "team"]].drop_duplicates().iloc[0]
    sub = wide[(wide["game_id"] == sample_key["game_id"]) &
               (wide["team"] == sample_key["team"])].sort_values("pulled_at")
    fig, ax = plt.subplots(figsize=(10, 5))
    for b in books:
        ax.plot(sub["pulled_at"], sub[b], label=b, alpha=0.7)
    ax.plot(sub["pulled_at"], sub["consensus"], label="consensus",
            color="black", linewidth=2)
    ax.set_title(f"Implied probability over time — {sample_key['team']} ({sample_key['game_id']})")
    ax.set_xlabel("time"); ax.set_ylabel("implied probability")
    ax.legend(loc="best", fontsize=8)
    save_plot(fig, "01_consensus_over_time.png")

    # MSE per book
    print("\n=== MSE vs consensus ===")
    print(res["mse_per_book"])
    fig, ax = plt.subplots(figsize=(8, 4))
    res["mse_per_book"].plot.bar(ax=ax)
    ax.set_title("MSE of each book vs consensus")
    ax.set_ylabel("MSE")
    save_plot(fig, "02_mse_per_book.png")

    # deviation distribution
    devs = res["deviation_table"]
    if not devs.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        sns.boxplot(data=devs, x="book", y="deviation", ax=ax)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title("Deviation from consensus by book")
        plt.xticks(rotation=30, ha="right")
        save_plot(fig, "03_deviation_box.png")

    # lead-lag heatmap
    print("\n=== Leader scores ===")
    print(res["leader_scores"])
    mat = res["lag_matrix"].astype(float)
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(mat, annot=True, cmap="vlag", center=0, ax=ax)
    ax.set_title("Best lag of row vs col (positive = row leads col)")
    save_plot(fig, "04_lead_lag_heatmap.png")

    # prediction
    print("\n=== Prediction ===")
    pred = res["prediction"]
    if "error" in pred:
        print(pred["error"])
    else:
        print(f"logreg accuracy: {pred['logreg_accuracy']:.3f}")
        print(f"random forest accuracy: {pred['rf_accuracy']:.3f}")
        print(f"baseline (always majority class): {pred['baseline_accuracy']:.3f}")
        fig, ax = plt.subplots(figsize=(8, 4))
        pred["feature_importance"].plot.bar(ax=ax)
        ax.set_title("Random forest feature importance")
        plt.xticks(rotation=45, ha="right")
        save_plot(fig, "05_feature_importance.png")

    # clustering
    print("\n=== Clusters ===")
    print(res["cluster_summary"])
    print(f"silhouette score: {res['cluster_silhouette']}")
    cf = res["cluster_features"]
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.scatterplot(
        data=cf, x="mean_disagreement", y="consensus_change",
        hue="cluster", palette="tab10", ax=ax,
    )
    ax.set_title("Market regimes (k-means clusters)")
    save_plot(fig, "06_clusters.png")

    # anomalies
    print("\n=== Anomalies ===")
    print(res["anomaly_followup"])
    af = res["anomaly_features"]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(af["pulled_at"], af["mean_consensus"], label="mean consensus",
            color="steelblue")
    flagged = af[af["is_anomaly"] == 1]
    ax.scatter(flagged["pulled_at"], flagged["mean_consensus"],
               color="red", label="anomaly", zorder=5)
    ax.set_title("Anomalies on the consensus path")
    ax.legend()
    save_plot(fig, "07_anomalies.png")

    # combined score
    cs = res["combined"]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(cs["pulled_at"], cs["combined"], color="darkorange")
    ax.set_title("Combined market-attention score over time")
    ax.set_ylabel("score (0..1)")
    save_plot(fig, "08_combined_score.png")

    print("\nAll outputs saved to", OUT_DIR)


if __name__ == "__main__":
    main()
