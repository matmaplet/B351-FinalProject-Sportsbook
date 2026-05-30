import numpy as np
import pandas as pd

from .data_loader import book_columns


def add_consensus(wide, weighted=False):
    books = book_columns(wide)
    vals = wide[books]

    if not weighted:
        wide["consensus"] = vals.mean(axis=1, skipna=True)
        return wide

    # weight each book by 1/variance so jittery books count for less
    book_var = vals.var(axis=0, skipna=True).replace(0, np.nan)
    weights = 1.0 / book_var
    weights = weights.fillna(0.0)
    if weights.sum() == 0:
        wide["consensus"] = vals.mean(axis=1, skipna=True)
        return wide

    weighted_sum = (vals * weights).sum(axis=1, skipna=True)
    weight_total = vals.notna().mul(weights, axis=1).sum(axis=1)
    wide["consensus"] = weighted_sum / weight_total.replace(0, np.nan)
    return wide


def deviation_table(wide):
    books = book_columns(wide)
    rows = []
    for b in books:
        d = wide[b] - wide["consensus"]
        for v in d.dropna():
            rows.append({"book": b, "deviation": v})
    return pd.DataFrame(rows)


def mse_per_book(wide):
    books = book_columns(wide)
    out = {}
    for b in books:
        diff = (wide[b] - wide["consensus"]).dropna()
        if len(diff) == 0:
            continue
        out[b] = float((diff ** 2).mean())
    return pd.Series(out).sort_values()
