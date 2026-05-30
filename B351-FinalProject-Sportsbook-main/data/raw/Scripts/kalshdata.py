import requests
import csv
import os
import re
from datetime import datetime, timezone

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2/markets"

# Single-game moneyline series on Kalshi
SERIES = {
    "MLB": "KXMLBGAME",
    "NBA": "KXNBAGAME",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(SCRIPT_DIR, "..", "csv_files", "raw_kalshi.csv")

COLS = [
    "pulled_at",
    "sport",
    "series_ticker",
    "event_ticker",
    "market_ticker",
    "title",
    "yes_team",
    "no_team",
    "game_date",
    "yes_bid",
    "yes_ask",
    "yes_mid",
    "last_price",
    "volume_24h",
    "volume_total",
    "open_interest",
    "liquidity",
    "close_time",
    "status",
]


def parse_game_date(event_ticker):
    # KXMLBGAME-26APR232005PITTEX  or  KXNBAGAME-26APR27OKCPHX
    m = re.search(r"-(\d{2})([A-Z]{3})(\d{2})", event_ticker or "")
    if not m:
        return ""

    yy, mon, dd = m.groups()
    months = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
        "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
        "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
    }
    if mon not in months:
        return ""
    return f"20{yy}-{months[mon]}-{dd}"


def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fetch_series(series_ticker):
    cursor = None
    markets = []

    while True:
        params = {"series_ticker": series_ticker, "limit": 200}
        if cursor:
            params["cursor"] = cursor

        r = requests.get(BASE_URL, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        markets.extend(data.get("markets", []))

        cursor = data.get("cursor")
        if not cursor:
            break

    return markets


def build_rows(sport, series_ticker, markets, pulled_at):
    rows = []
    for m in markets:
        yes_bid = to_float(m.get("yes_bid_dollars"))
        yes_ask = to_float(m.get("yes_ask_dollars"))
        yes_mid = None
        if yes_bid is not None and yes_ask is not None:
            yes_mid = round((yes_bid + yes_ask) / 2, 4)

        rows.append([
            pulled_at,
            sport,
            series_ticker,
            m.get("event_ticker"),
            m.get("ticker"),
            m.get("title"),
            m.get("yes_sub_title"),
            m.get("no_sub_title"),
            parse_game_date(m.get("event_ticker")),
            yes_bid,
            yes_ask,
            yes_mid,
            to_float(m.get("last_price_dollars")),
            to_float(m.get("volume_24h_fp")),
            to_float(m.get("volume_fp")),
            to_float(m.get("open_interest_fp")),
            to_float(m.get("liquidity_dollars")),
            m.get("close_time"),
            m.get("status"),
        ])
    return rows


def save(rows):
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    new_file = not os.path.exists(OUT_FILE) or os.path.getsize(OUT_FILE) == 0

    with open(OUT_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(COLS)
        for r in rows:
            w.writerow(r)


def main():
    pulled_at = datetime.now(timezone.utc).isoformat()
    all_rows = []

    for sport, series_ticker in SERIES.items():
        markets = fetch_series(series_ticker)
        rows = build_rows(sport, series_ticker, markets, pulled_at)
        all_rows.extend(rows)
        print(f"{sport} ({series_ticker}): {len(rows)} markets")

    save(all_rows)
    print("saved", len(all_rows), "rows to", OUT_FILE)


if __name__ == "__main__":
    main()
