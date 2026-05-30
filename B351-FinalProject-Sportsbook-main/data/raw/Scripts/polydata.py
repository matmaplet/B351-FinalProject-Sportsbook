import requests
import csv
import os
import json
from datetime import datetime, timezone


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KALSHI_FILE = os.path.join(SCRIPT_DIR, "..", "csv_files", "raw_kalshi.csv")
POLY_FILE = os.path.join(SCRIPT_DIR, "..", "csv_files", "raw_polymarket.csv")


def save_csv(file_name, cols, rows):
    new_file = not os.path.exists(file_name)

    with open(file_name, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)

        if new_file:
            w.writerow(cols)

        for row in rows:
            w.writerow(row)


def get_sport_name(text):
    t = (text or "").lower()

    if "nba" in t or "basketball" in t:
        return "NBA"
    if "mlb" in t or "baseball" in t:
        return "MLB"
    return None



def parse_list(x):
    if isinstance(x, list):
        return x
    if isinstance(x, str):
        try:
            return json.loads(x)
        except:
            return []
    return []


def get_poly_sport_tags():
    url = "https://gamma-api.polymarket.com/sports"

    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()

    tags = {}

    for x in data:
        sport = (x.get("sport") or "").lower()
        raw_tags = x.get("tags") or ""
        tag_list = [s.strip() for s in raw_tags.split(",") if s.strip()]

        if sport == "nba":
            tags["NBA"] = tag_list
        elif sport == "mlb":
            tags["MLB"] = tag_list

    return tags


def fetch_polymarket():
    sport_tags = get_poly_sport_tags()
    pulled_at = datetime.now(timezone.utc).isoformat()
    rows = []

    for sport, tags in sport_tags.items():
        for tag in tags:
            url = "https://gamma-api.polymarket.com/events"
            params = {
                "tag_id": tag,
                "active": "true",
                "closed": "false",
                "limit": 100,
            }

            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            events = r.json()

            for event in events:
                event_id = event.get("id")
                event_title = event.get("title")
                end_date = event.get("endDate")

                for market in event.get("markets", []):
                    outcomes = parse_list(market.get("outcomes"))
                    prices = parse_list(market.get("outcomePrices"))

                    n = min(len(outcomes), len(prices))

                    for i in range(n):
                        rows.append([
                            pulled_at,
                            sport,
                            event_id,
                            event_title,
                            market.get("id"),
                            market.get("question"),
                            outcomes[i],
                            prices[i],
                            end_date,
                            market.get("active"),
                            market.get("closed"),
                            market.get("liquidity"),
                            market.get("volume"),
                        ])

    cols = [
        "pulled_at",
        "sport",
        "event_id",
        "event_title",
        "market_id",
        "question",
        "outcome",
        "price",
        "end_date",
        "active",
        "closed",
        "liquidity",
        "volume",
    ]

    save_csv(POLY_FILE, cols, rows)
    print("saved", len(rows), "polymarket rows")


def main():
    fetch_polymarket()


if __name__ == "__main__":
    main()