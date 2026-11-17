"""Fetch daily defender-distance tracking and matched NBA game denominators."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from bbb_triples import get_json, SCHEDULE_URL, season_for, slate_from_schedule, stats_url
from method_policy import metadata

BUCKETS = ["0-2 Feet - Very Tight", "2-4 Feet - Tight", "4-6 Feet - Open", "6+ Feet - Wide Open"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=datetime.now(ZoneInfo("America/Chicago")).date().isoformat())
    parser.add_argument("--out", type=Path, default=Path("tracking/current"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    slate = date.fromisoformat(args.date)
    cutoff, season = slate-timedelta(days=1), season_for(slate)
    args.out.mkdir(parents=True, exist_ok=True)
    raw = args.out / "raw"
    schedule, schedule_source = get_json(SCHEDULE_URL, raw, args.offline)
    slate_from_schedule(schedule, slate, season)  # validates season and NBA team universe
    games = []
    seen = set()
    for entry in schedule["leagueSchedule"]["gameDates"]:
        day = datetime.strptime(entry["gameDate"].split()[0], "%m/%d/%Y").date()
        if day > cutoff:
            continue
        for game in entry["games"]:
            gid = str(game["gameId"])
            if not gid.startswith("002") or game["gameStatus"] != 3:
                continue
            if gid in seen:
                raise ValueError("Duplicate completed game in schedule")
            seen.add(gid)
            games.append({"id": gid, "date": day.isoformat(),
                "home_id": int(game["homeTeam"]["teamId"]), "away_id": int(game["awayTeam"]["teamId"]),
                "home": game["homeTeam"]["teamTricode"], "away": game["awayTeam"]["teamTricode"]})
    jobs = []
    for day_text in sorted({g["date"] for g in games}):
        day = date.fromisoformat(day_text)
        date_filter = day.strftime("%m/%d/%Y")
        advanced = stats_url(season, day, 0, "Advanced").replace(
            "DateFrom=&", "DateFrom=" + date_filter.replace("/", "%2F") + "&")
        jobs.append((day_text, "advanced", advanced))
        for i, bucket in enumerate(BUCKETS):
            p = dict(PerMode="Totals", LeagueID="00", Season=season, SeasonYear=season,
                SeasonType="Regular Season", PORound=0, CloseDefDistRange=bucket,
                ShotClockRange="", ShotDistRange="", TouchTimeRange="", DribbleRange="",
                GeneralRange="Overall", TeamID=0, Outcome="", Location="", Month=0,
                SeasonSegment="", DateFrom=date_filter, DateTo=date_filter, OpponentTeamID=0,
                VsConference="", VsDivision="", Conference="", Division="", GameSegment="",
                Period=0, LastNGames=0)
            jobs.append((day_text, str(i), "https://stats.nba.com/stats/leaguedashoppptshot?" + urlencode(p)))

    def fetch(job):
        day, kind, url = job
        try:
            payload, source = get_json(url, raw, args.offline, timeout=15)
            return {"date": day, "kind": kind, "payload": payload, "source": source}
        except Exception as error:
            return {"date": day, "kind": kind, "error": str(error), "url": url}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        responses = list(pool.map(fetch, jobs))
    output = {"cutoff": cutoff.isoformat(), "season": season, "slate_date": slate.isoformat(),
              "games": games, "responses": responses, "schedule_source": schedule_source, "method": metadata()}
    (args.out / "inputs.json").write_text(json.dumps(output))
    box_params = dict(LeagueID="00", Season=season, SeasonType="Regular Season", PlayerOrTeam="T",
                      Counter=0, Sorter="DATE", Direction="DESC", DateFrom="", DateTo=cutoff.strftime("%m/%d/%Y"))
    payload, source = get_json("https://stats.nba.com/stats/leaguegamelog?" + urlencode(sorted(box_params.items())), raw, args.offline)
    (args.out / "boxlogs.json").write_text(json.dumps({"payload": payload, "source": source}))
    errors = [r for r in responses if "error" in r]
    print(json.dumps({"games": len(games), "requests": len(responses), "failures": len(errors),
                      "cutoff": cutoff.isoformat(), "offline": args.offline}))
    if errors:
        raise SystemExit("Tracking requests failed; inspect inputs.json before analysis")


if __name__ == "__main__":
    main()
