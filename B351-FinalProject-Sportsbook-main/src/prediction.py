import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score


def build_features(wide_with_consensus, books, n_lags=3, vol_window=5):
    df = wide_with_consensus.sort_values(["game_id", "team", "pulled_at"]).copy()

    # label = does the consensus go up next step?
    df["consensus_next"] = df.groupby(["game_id", "team"])["consensus"].shift(-1)
    df["delta_next"] = df["consensus_next"] - df["consensus"]
    df["y"] = (df["delta_next"] > 0).astype(int)

    for k in range(1, n_lags + 1):
        df[f"d_lag_{k}"] = df.groupby(["game_id", "team"])["consensus"].diff(k)

    # rolling volatility
    df["vol"] = (
        df.groupby(["game_id", "team"])["consensus"]
        .rolling(vol_window, min_periods=2)
        .std()
        .reset_index(level=[0, 1], drop=True)
    )

    dev_cols = []
    for b in books:
        col = f"dev_{b}"
        df[col] = df[b] - df["consensus"]
        dev_cols.append(col)

    feat_cols = [f"d_lag_{k}" for k in range(1, n_lags + 1)] + ["vol"] + dev_cols
    df = df.dropna(subset=feat_cols + ["y", "delta_next"])

    return df, feat_cols


def split_train_test(df, test_frac=0.2):
    df = df.sort_values("pulled_at").reset_index(drop=True)
    n = len(df)
    cut = int(n * (1 - test_frac))
    return df.iloc[:cut], df.iloc[cut:]


def train_and_eval(wide_with_consensus, books):
    df, feat_cols = build_features(wide_with_consensus, books)
    if len(df) < 30:
        return {"error": "not enough rows to train (need ~30+)"}

    train, test = split_train_test(df)
    X_train, y_train = train[feat_cols].values, train["y"].values
    X_test, y_test = test[feat_cols].values, test["y"].values

    logreg = LogisticRegression(max_iter=1000)
    logreg.fit(X_train, y_train)
    p_log = logreg.predict(X_test)

    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    p_rf = rf.predict(X_test)

    importances = pd.Series(rf.feature_importances_, index=feat_cols).sort_values(
        ascending=False
    )

    return {
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "logreg_accuracy": float(accuracy_score(y_test, p_log)),
        "rf_accuracy": float(accuracy_score(y_test, p_rf)),
        "baseline_accuracy": float(max(np.mean(y_test), 1 - np.mean(y_test))),
        "feature_importance": importances,
        "logreg": logreg,
        "rf": rf,
        "feat_cols": feat_cols,
    }
