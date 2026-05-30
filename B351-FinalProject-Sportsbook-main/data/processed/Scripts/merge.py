"""
Merge the three raw feeds (sportsbook odds, Kalshi, Polymarket) into a single
long-format CSV where every row is one (source, market, outcome) quote expressed
as an implied probability.

Output schema (unified_odds.csv):
    pulled_at       ISO timestamp of the pull
    source          odds | kalshi | polymarket
    sport           MLB | NBA
    game_date       YYYY-MM-DD (UTC)
    commence_time   ISO timestamp when known, else blank
    home_team       normalized team name (blank for markets that don't expose it)
    away_team       normalized team name (blank when unknown)
    team            normalized team this quote is FOR (the "yes" side)
    bookmaker       sportsbook name for odds, else the source
    implied_prob    0..1 probability implied by the quoted price
    raw_price       original price string (American odds, Kalshi yes_ask, Poly price)
    source_event_id vendor event id
    source_market_id vendor market id (blank for odds rows)
    extra           free-form JSON string with source-specific fields
"""

import csv
import json
import os
import re
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "..", "..", "raw", "csv_files")
OUT_DIR = os.path.join(SCRIPT_DIR, "..", "csv_files")
OUT_FILE = os.path.join(OUT_DIR, "unified_odds.csv")

ODDS_FILE = os.path.join(RAW_DIR, "raw_odds.csv")
KALSHI_FILE = os.path.join(RAW_DIR, "raw_kalshi.csv")
POLY_FILE = os.path.join(RAW_DIR, "raw_polymarket.csv")

UNIFIED_COLS = [
    "pulled_at",
    "source",
    "sport",
    "game_date",
    "commence_time",
    "home_team",
    "away_team",
    "team",
    "bookmaker",
    "implied_prob",
    "raw_price",
    "source_event_id",
    "source_market_id",
    "extra",
]

SPORT_MAP = {
    "baseball_mlb": "MLB",
    "basketball_nba": "NBA",
    "mlb": "MLB",
    "nba": "NBA",
}

# Team-name aliases -> canonical full name. Covers the shorthand Kalshi uses in
# yes_sub_title and the bare-city forms Polymarket questions sometimes use.
TEAM_ALIASES = {
    # MLB
    "arizona": "Arizona Diamondbacks",
    "atlanta": "Atlanta Braves",
    "baltimore": "Baltimore Orioles",
    "boston": "Boston Red Sox",
    "chicago c": "Chicago Cubs",
    "chicago w": "Chicago White Sox",
    "chicago ws": "Chicago White Sox",
    "cincinnati": "Cincinnati Reds",
    "cleveland": "Cleveland Guardians",
    "colorado": "Colorado Rockies",
    "detroit": "Detroit Tigers",
    "houston": "Houston Astros",
    "kansas city": "Kansas City Royals",
    "los angeles a": "Los Angeles Angels",
    "los angeles d": "Los Angeles Dodgers",
    "miami": "Miami Marlins",
    "milwaukee": "Milwaukee Brewers",
    "minnesota": "Minnesota Twins",
    "new york m": "New York Mets",
    "new york y": "New York Yankees",
    "a's": "Oakland Athletics",
    "oakland": "Oakland Athletics",
    "athletics": "Oakland Athletics",
    "philadelphia": "Philadelphia Phillies",
    "pittsburgh": "Pittsburgh Pirates",
    "san diego": "San Diego Padres",
    "san francisco": "San Francisco Giants",
    "seattle": "Seattle Mariners",
    "st. louis": "St. Louis Cardinals",
    "st louis": "St. Louis Cardinals",
    "tampa bay": "Tampa Bay Rays",
    "texas": "Texas Rangers",
    "toronto": "Toronto Blue Jays",
    "washington": "Washington Nationals",
    # NBA
    "atlanta hawks": "Atlanta Hawks",
    "boston celtics": "Boston Celtics",
    "brooklyn": "Brooklyn Nets",
    "charlotte": "Charlotte Hornets",
    "chicago bulls": "Chicago Bulls",
    "cleveland cavaliers": "Cleveland Cavaliers",
    "dallas": "Dallas Mavericks",
    "denver": "Denver Nuggets",
    "detroit pistons": "Detroit Pistons",
    "golden state": "Golden State Warriors",
    "houston rockets": "Houston Rockets",
    "indiana": "Indiana Pacers",
    "la clippers": "LA Clippers",
    "los angeles clippers": "LA Clippers",
    "los angeles c": "LA Clippers",
    "los angeles lakers": "Los Angeles Lakers",
    "los angeles l": "Los Angeles Lakers",
    "memphis": "Memphis Grizzlies",
    "miami heat": "Miami Heat",
    "milwaukee bucks": "Milwaukee Bucks",
    "minnesota timberwolves": "Minnesota Timberwolves",
    "new orleans": "New Orleans Pelicans",
    "new york": "New York Knicks",
    "oklahoma city": "Oklahoma City Thunder",
    "orlando": "Orlando Magic",
    "philadelphia 76ers": "Philadelphia 76ers",
    "phoenix": "Phoenix Suns",
    "portland": "Portland Trail Blazers",
    "sacramento": "Sacramento Kings",
    "san antonio": "San Antonio Spurs",
    "toronto raptors": "Toronto Raptors",
    "utah": "Utah Jazz",
    "washington wizards": "Washington Wizards",
}


def normalize_team(name):
    if not name:
        return ""
    key = name.strip().lower()
    if key in TEAM_ALIASES:
        return TEAM_ALIASES[key]
    # Already a full team name? Keep it as given.
    return name.strip()


# Canonical MLB and NBA team names. Used to drop Polymarket rows whose
# extracted "team" isn't actually one of the 60 teams we care about
# (Polymarket's loose MLB/NBA tag IDs include cross-sport futures and
# other non-game markets that would otherwise pollute the dropdown).
KNOWN_TEAMS = set(TEAM_ALIASES.values())


def american_to_prob(price_str):
    try:
        p = float(price_str)
    except (TypeError, ValueError):
        return None
    if p > 0:
        return 100.0 / (p + 100.0)
    if p < 0:
        return -p / (-p + 100.0)
    return None


def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def date_from_iso(ts):
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return ts[:10] if len(ts) >= 10 else ""


def read_csv(path):
    if not os.path.exists(path):
        print(f"warn: missing {path}")
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def transform_odds(rows):
    out = []
    for r in rows:
        sport = SPORT_MAP.get((r.get("sport") or "").lower(), r.get("sport"))
        if r.get("market") != "h2h":
            continue
        prob = american_to_prob(r.get("price"))
        if prob is None:
            continue
        home = normalize_team(r.get("home_team"))
        away = normalize_team(r.get("away_team"))
        team = normalize_team(r.get("outcome"))

        out.append({
            "pulled_at": r.get("pulled_at"),
            "source": "odds",
            "sport": sport,
            "game_date": date_from_iso(r.get("commence_time")),
            "commence_time": r.get("commence_time"),
            "home_team": home,
            "away_team": away,
            "team": team,
            "bookmaker": r.get("bookmaker"),
            "implied_prob": round(prob, 6),
            "raw_price": r.get("price"),
            "source_event_id": r.get("event_id"),
            "source_market_id": "",
            "extra": json.dumps({"book_last_update": r.get("book_last_update")}),
        })
    return out


def transform_kalshi(rows):
    # Kalshi's `yes_team` and `no_team` are the descriptions of the YES
    # and NO outcomes for ONE side ("Utah wins" / "Utah doesn't win"),
    # not the two opposing teams. To find the actual opponent we have
    # to group all markets under the same event_ticker and look at
    # which other team appears in that event.
    teams_by_event = {}
    for r in rows:
        ev = r.get("event_ticker")
        team = normalize_team(r.get("yes_team"))
        if ev and team:
            teams_by_event.setdefault(ev, set()).add(team)

    out = []
    for r in rows:
        # Drop anything the old broken puller left behind — only keep rows that
        # match the new schema.
        if "yes_team" not in r or not r.get("yes_team"):
            continue
        prob = to_float(r.get("yes_ask"))
        if prob is None:
            prob = to_float(r.get("yes_mid"))
        if prob is None:
            continue

        team = normalize_team(r.get("yes_team"))
        ev = r.get("event_ticker")
        others = teams_by_event.get(ev, set()) - {team}
        opponent = next(iter(others), "") if others else ""
        # If the event only contained one team's market in this pull
        # (rare — usually paired markets), we can't form a matchup.
        # Drop these so the dropdown stays clean.
        if not opponent:
            continue

        out.append({
            "pulled_at": r.get("pulled_at"),
            "source": "kalshi",
            "sport": r.get("sport"),
            "game_date": r.get("game_date") or date_from_iso(r.get("close_time")),
            "commence_time": r.get("close_time") or "",
            # Both teams populated so to_wide() can build a proper game
            # label. Single-game Kalshi markets don't have a true
            # home/away — these are just "the two teams playing".
            "home_team": team,
            "away_team": opponent,
            "team": team,
            "bookmaker": "Kalshi",
            "implied_prob": round(prob, 6),
            "raw_price": r.get("yes_ask"),
            "source_event_id": r.get("event_ticker"),
            "source_market_id": r.get("market_ticker"),
            "extra": json.dumps({
                "title": r.get("title"),
                "opponent": opponent,
                "yes_bid": r.get("yes_bid"),
                "yes_mid": r.get("yes_mid"),
                "last_price": r.get("last_price"),
                "volume_24h": r.get("volume_24h"),
                "status": r.get("status"),
            }),
        })
    return out


# Polymarket questions are usually shaped like "Will the X beat the Y?" or
# "Will the X win ...?". Extract the team the "Yes" side pays out on.
WILL_BEAT = re.compile(r"will\s+the\s+(.+?)\s+beat\s+the\s+(.+?)\?", re.IGNORECASE)
WILL_WIN = re.compile(r"will\s+the\s+(.+?)\s+win", re.IGNORECASE)


def extract_poly_teams(question, outcome):
    if not question:
        return "", "", ""
    m = WILL_BEAT.search(question)
    if m:
        a, b = m.group(1).strip(), m.group(2).strip()
        if outcome and outcome.lower() == "yes":
            return normalize_team(a), normalize_team(a), normalize_team(b)
        if outcome and outcome.lower() == "no":
            return normalize_team(b), normalize_team(a), normalize_team(b)
    m = WILL_WIN.search(question)
    if m:
        team = normalize_team(m.group(1).strip())
        if outcome and outcome.lower() == "yes":
            return team, team, ""
        if outcome and outcome.lower() == "no":
            return "", team, ""
    return "", "", ""


def transform_polymarket(rows):
    out = []
    for r in rows:
        sport = SPORT_MAP.get((r.get("sport") or "").lower(), r.get("sport"))
        prob = to_float(r.get("price"))
        if prob is None:
            continue

        team, a, b = extract_poly_teams(r.get("question"), r.get("outcome"))
        # Drop anything that isn't a real game between two known
        # MLB/NBA teams. Polymarket's MLB/NBA tags include cross-sport
        # futures and championship-style "Will X win?" questions
        # without an identified opponent — without this filter they
        # show up in the dashboard dropdown as single-team entries.
        if team not in KNOWN_TEAMS or b not in KNOWN_TEAMS:
            continue

        out.append({
            "pulled_at": r.get("pulled_at"),
            "source": "polymarket",
            "sport": sport,
            "game_date": date_from_iso(r.get("end_date")),
            "commence_time": r.get("end_date"),
            # `a` is the team the question is built around ("Will the
            # A beat the B?"), `b` is the other team. Filling both so
            # to_wide() can pair Polymarket rows with the matching
            # Kalshi/Sportsbook rows for the same game.
            "home_team": a,
            "away_team": b,
            "team": team,
            "bookmaker": "Polymarket",
            "implied_prob": round(prob, 6),
            "raw_price": r.get("price"),
            "source_event_id": r.get("event_id"),
            "source_market_id": r.get("market_id"),
            "extra": json.dumps({
                "event_title": r.get("event_title"),
                "question": r.get("question"),
                "outcome": r.get("outcome"),
                "liquidity": r.get("liquidity"),
                "volume": r.get("volume"),
                "active": r.get("active"),
                "closed": r.get("closed"),
            }),
        })
    return out


def write_unified(rows):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=UNIFIED_COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    odds = transform_odds(read_csv(ODDS_FILE))
    kalshi = transform_kalshi(read_csv(KALSHI_FILE))
    poly = transform_polymarket(read_csv(POLY_FILE))

    all_rows = odds + kalshi + poly
    write_unified(all_rows)

    print(f"odds rows:       {len(odds)}")
    print(f"kalshi rows:     {len(kalshi)}")
    print(f"polymarket rows: {len(poly)}")
    print(f"wrote {len(all_rows)} rows to {OUT_FILE}")


if __name__ == "__main__":
    main()
