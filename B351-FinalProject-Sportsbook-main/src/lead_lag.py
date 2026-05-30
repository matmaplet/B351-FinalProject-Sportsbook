import numpy as np
import pandas as pd


def book_series(wide_with_consensus, book):
    return wide_with_consensus.groupby("pulled_at")[book].mean().sort_index()


def cross_correlation(a, b, max_lag=5):
    # pearson corr of a(t) vs b(t+lag)
    a = a.dropna()
    b = b.dropna()
    common = a.index.intersection(b.index)
    if len(common) < 3:
        return {}
    a = a.loc[common].values
    b = b.loc[common].values

    out = {}
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            x, y = a[-lag:], b[:lag]
        elif lag > 0:
            x, y = a[:-lag], b[lag:]
        else:
            x, y = a, b
        if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
            continue
        out[lag] = float(np.corrcoef(x, y)[0, 1])
    return out


def best_lag(corr_dict):
    if not corr_dict:
        return 0, 0.0
    lag, val = max(corr_dict.items(), key=lambda kv: kv[1])
    return lag, val


def leader_scores(wide_with_consensus, books, max_lag=5):
    # positive score = this book tends to move first
    scores = {}
    for a in books:
        sa = book_series(wide_with_consensus, a)
        lags = []
        for b in books:
            if b == a:
                continue
            sb = book_series(wide_with_consensus, b)
            corr = cross_correlation(sa, sb, max_lag=max_lag)
            lag, _ = best_lag(corr)
            lags.append(lag)
        scores[a] = float(np.mean(lags)) if lags else 0.0
    return pd.Series(scores).sort_values(ascending=False)


def pairwise_lag_matrix(wide_with_consensus, books, max_lag=5):
    mat = pd.DataFrame(index=books, columns=books, dtype=float)
    for a in books:
        sa = book_series(wide_with_consensus, a)
        for b in books:
            if a == b:
                mat.loc[a, b] = 0.0
                continue
            sb = book_series(wide_with_consensus, b)
            corr = cross_correlation(sa, sb, max_lag=max_lag)
            lag, _ = best_lag(corr)
            mat.loc[a, b] = lag
    return mat
