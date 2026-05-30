# Two evaluation figures for the report:
#   1. prediction model comparison (logreg vs RF vs majority baseline)
#   2. lead-lag leader recovery (does our score put the simulator's true leader on top?)

import os
import sys

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline import run_all

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs"
)
TRUE_LEADER = "BetMGM"  # set by src/simulate.py


def main():
    res = run_all(use_simulation=True)

    # prediction comparison
    pred = res["prediction"]
    pred_df = pd.DataFrame(
        {
            "Model": ["Majority baseline", "Logistic regression", "Random forest"],
            "Accuracy": [
                pred["baseline_accuracy"],
                pred["logreg_accuracy"],
                pred["rf_accuracy"],
            ],
        }
    )
    print(pred_df.to_string(index=False))

    fig, ax = plt.subplots(figsize=(6, 3.5))
    bars = ax.bar(pred_df["Model"], pred_df["Accuracy"],
                  color=["#bbb", "#4c78a8", "#e45756"])
    for b, v in zip(bars, pred_df["Accuracy"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.01,
                f"{v:.3f}", ha="center", fontsize=10)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Accuracy on held-out tail")
    ax.set_title("Next-step direction prediction")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "eval_01_prediction_comparison.png"), dpi=150)
    plt.close(fig)

    # leader recovery
    scores = res["leader_scores"].sort_values(ascending=True)
    rank_of_true = list(res["leader_scores"].index).index(TRUE_LEADER) + 1

    print(f"\nTrue leader = {TRUE_LEADER} | recovered rank = {rank_of_true} of {len(scores)}")
    print(res["leader_scores"])

    fig, ax = plt.subplots(figsize=(6, 4.5))
    colors = ["#e45756" if b == TRUE_LEADER else "#4c78a8" for b in scores.index]
    ax.barh(scores.index, scores.values, color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Leader score (positive = leads)")
    ax.set_title(f"Lead-lag recovery — true leader = {TRUE_LEADER} (red), recovered rank {rank_of_true}/{len(scores)}")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "eval_02_leader_recovery.png"), dpi=150)
    plt.close(fig)

    summary = pd.DataFrame(
        [
            ["Majority baseline accuracy", round(pred["baseline_accuracy"], 4)],
            ["Logistic regression accuracy", round(pred["logreg_accuracy"], 4)],
            ["Random forest accuracy", round(pred["rf_accuracy"], 4)],
            ["True simulator leader", TRUE_LEADER],
            ["Recovered leader rank (1 = best)", rank_of_true],
            ["Books ranked", len(scores)],
        ],
        columns=["Metric", "Value"],
    )
    summary.to_csv(os.path.join(OUT_DIR, "eval_summary.csv"), index=False)
    print("\nWrote:", os.path.join(OUT_DIR, "eval_summary.csv"))


if __name__ == "__main__":
    main()
