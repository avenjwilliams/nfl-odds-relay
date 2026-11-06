#!/usr/bin/env python3
"""Fetch NFL game lines and player props for one slate date from every US sportsbook on
The Odds API and save them for the nfl-slate-research skill.

Runs inside GitHub Actions (normal internet access) and writes:
    odds/<YYYY-MM-DD>.json   everything for games on that date (America/Chicago)
    odds/latest.json         copy of the newest pull
Env:
    ODDS_API_KEY      required (repo secret)
    SLATE_DATE        optional YYYY-MM-DD; default = today in America/Chicago
    MIN_CREDITS_LEFT  optional; skip prop pulls that would drop below this (default 10)
Credit cost (The Odds API bills markets x regions, not per book):
    game lines = 3 per pull; props = len(PROP_MARKETS) per game.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

API = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
REGION = "us"
GAME_MARKETS = "h2h,spreads,totals"
PROP_MARKETS = ["player_pass_yds", "player_pass_tds", "player_rush_yds",
                "player_reception_yds", "player_receptions", "player_anytime_td"]
CT = ZoneInfo("America/Chicago")
UA = {"User-Agent": "nfl-odds-relay/1.0"}


def http_json(url, retries=4):
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r), r.headers
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2 ** attempt)  # back off on rate limits: 1, 2, 4, 8 s
                continue
            raise


def odds_get(path, **params):
    params["apiKey"] = os.environ["ODDS_API_KEY"]
    data, headers = http_json(f"{API}{path}?{urllib.parse.urlencode(params)}")
    remaining = headers.get("x-requests-remaining")
    return data, (int(float(remaining)) if remaining else None)


def fetch_sportsbooks(slate, notes):
    floor = int(os.environ.get("MIN_CREDITS_LEFT", "10"))
    day = datetime.fromisoformat(slate).replace(tzinfo=CT)
    lo, hi = day, day + timedelta(days=1)
    events, remaining = odds_get("/events")  # free endpoint
    todays = [e for e in events
              if lo <= datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")).astimezone(CT) < hi]
    games = []
    if not todays:
        notes.append("No NFL games on this date at The Odds API.")
        return games, remaining
    lines, remaining = odds_get("/odds", regions=REGION, markets=GAME_MARKETS, oddsFormat="american")
    by_id = {g["id"]: g for g in lines}
    for e in sorted(todays, key=lambda x: x["commence_time"]):
        g = {"id": e["id"], "commence_time": e["commence_time"], "home_team": e["home_team"],
             "away_team": e["away_team"],
             "game_books": by_id.get(e["id"], {}).get("bookmakers", []),
             "prop_books": []}
        cost = len(PROP_MARKETS)
        label = f"{e['away_team']} @ {e['home_team']}"
        if remaining is not None and remaining - cost < floor:
            notes.append(f"Skipped props for {label}: only {remaining} credits left.")
        else:
            try:
                ev, remaining = odds_get(f"/events/{e['id']}/odds", regions=REGION,
                                         markets=",".join(PROP_MARKETS), oddsFormat="american")
                g["prop_books"] = ev.get("bookmakers", [])
                if not g["prop_books"]:
                    notes.append(f"No props posted yet for {label}.")
                elif not any(b["key"] == "fanduel" for b in g["prop_books"]):
                    notes.append(f"FanDuel props not posted yet for {label}; other books available.")
            except Exception as exc:
                notes.append(f"Prop pull failed for {label}: {exc}")
        games.append(g)
    return games, remaining


def main():
    slate = os.environ.get("SLATE_DATE") or datetime.now(CT).date().isoformat()
    notes = []
    try:
        games, remaining = fetch_sportsbooks(slate, notes)
    except Exception as exc:
        games, remaining = [], None
        notes.append(f"The Odds API pull failed: {exc}")
    out = {"slate_date": slate, "region": REGION, "fetched_at": datetime.now(timezone.utc).isoformat(),
           "credits_remaining": remaining, "notes": notes, "games": games}
    os.makedirs("odds", exist_ok=True)
    for path in (f"odds/{slate}.json", "odds/latest.json"):
        with open(path, "w") as f:
            json.dump(out, f, indent=1)
    nprops = sum(len(g["prop_books"]) for g in games)
    print(f"{slate}: {len(games)} games, {nprops} book prop feeds, credits left {remaining}")
    for n in notes:
        print("note:", n)


if __name__ == "__main__":
    if not os.environ.get("ODDS_API_KEY"):
        sys.exit("ODDS_API_KEY is not set. Add it as a repository secret.")
    main()
