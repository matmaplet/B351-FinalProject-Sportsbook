import requests
import csv
import os
import sys
from datetime import datetime, timezone

# Load variables from a local .env file if python-dotenv is installed.
# Falls back silently to the plain shell environment otherwise.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SPORT = "baseball_mlb"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTFILE = os.path.join(SCRIPT_DIR, "..", "csv_files", "raw_odds.csv")


def get_api_key():
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        sys.exit(
            "ODDS_API_KEY is not set. Either `export ODDS_API_KEY=your_key` "
            "or copy .env.example to .env and put the key there. "
            "See REFRESH_DATA.md."
        )
    return key


def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        "apiKey": get_api_key(),
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def save_rows(games, file_name):
    cols = [
        "pulled_at",
        "sport",
        "event_id",
        "commence_time",
        "home_team",
        "away_team",
        "bookmaker",
        "book_last_update",
        "market",
        "outcome",
        "price",
    ]

    new_file = not os.path.exists(file_name)

    with open(file_name, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)

        if new_file:
            w.writerow(cols)

        pulled_at = datetime.now(timezone.utc).isoformat()

        for game in games:
            sport = game["sport_key"]
            event_id = game["id"]
            commence_time = game["commence_time"]
            home_team = game["home_team"]
            away_team = game["away_team"]

            for book in game.get("bookmakers", []):
                bookmaker = book["title"]
                book_last_update = book["last_update"]

                for market in book.get("markets", []):
                    market_key = market["key"]

                    for outcome in market.get("outcomes", []):
                        row = [
                            pulled_at,
                            sport,
                            event_id,
                            commence_time,
                            home_team,
                            away_team,
                            bookmaker,
                            book_last_update,
                            market_key,
                            outcome["name"],
                            outcome["price"],
                        ]
                        w.writerow(row)


def main():
    games = fetch_odds()
    save_rows(games, OUTFILE)
    print("saved", len(games), "games to", OUTFILE)


if __name__ == "__main__":
    main()

