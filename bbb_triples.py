#!/usr/bin/env python3
"""BBB triples environment screener. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from method_policy import grounded_header, metadata

VERSION = "0.3.1"
METRICS = ("three_volume", "shooting", "oreb", "perimeter_vulnerability", "dreb_weakness", "pace")
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nba.com/",
           "Origin": "https://www.nba.com", "Accept": "application/json, text/plain, */*"}
STATS_URL = "https://stats.nba.com/stats/leaguedashteamstats"
SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
NBA_TEAM_IDS = set(range(1610612737, 1610612767))


def season_for(day):
    year = day.year if day.month >= 7 else day.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


def previous_season(season):
    year = int(season[:4]) - 1
    return f"{year}-{str(year + 1)[-2:]}"


def get_json(url, raw_dir, offline=False, timeout=20):
    """Exact-URL cache only. Every run records whether bytes were reused."""
    path = raw_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")
    if path.exists() and offline:
        envelope = json.loads(path.read_text())
        if envelope.get("url") != url:
            raise ValueError("Cache URL mismatch")
        return envelope["payload"], {"url": url, "file": path.name,
                                    "fetched_at": envelope["fetched_at"], "cache_reused": True}
    if offline:
        raise ValueError(f"Missing exact-request cache: {path.name}")
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout) as response:
                payload = json.load(response)
            break
        except (OSError, ValueError):
            if attempt:
                raise
            time.sleep(1)
    stamp = datetime.now(timezone.utc).isoformat()
    envelope = {"url": url, "fetched_at": stamp, "payload": payload}
    raw_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, separators=(",", ":")))
    return payload, {"url": url, "file": path.name, "fetched_at": stamp, "cache_reused": False}


def stats_url(season, cutoff, last_n, measure):
    from urllib.parse import urlencode
    params = dict(Conference="", DateFrom="", DateTo=cutoff.strftime("%m/%d/%Y"),
                  Division="", GameScope="", GameSegment="", LastNGames=last_n,
                  LeagueID="00", Location="", MeasureType=measure, Month=0,
                  OpponentTeamID=0, Outcome="", PORound=0, PaceAdjust="N",
                  PerMode="Per100Possessions", Period=0, PlayerExperience="",
                  PlayerPosition="", PlusMinus="N", Rank="N", Season=season,
                  SeasonSegment="", SeasonType="Regular Season", ShotClockRange="",
                  StarterBench="", TeamID=0, TwoWay=0, VsConference="", VsDivision="")
    return STATS_URL + "?" + urlencode(params)


def unpack(payload):
    sets = payload.get("resultSets", [])
    if isinstance(sets, dict):
        sets = [sets]
    table = next((s for s in sets if s.get("name") == "LeagueDashTeamStats"), None)
    if table is None:
        raise ValueError("Missing NBA LeagueDashTeamStats table")
    rows = [dict(zip(table["headers"], row, strict=True)) for row in table["rowSet"]]
    by_id = {int(r["TEAM_ID"]): r for r in rows}
    if len(by_id) != len(rows):
        raise ValueError("Duplicate team IDs")
    return by_id


def number(row, key, lo=0, hi=None):
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {key}: {value!r}")
    if value < lo or (hi is not None and value > hi):
        raise ValueError(f"Out-of-range {key}: {value}")
    return float(value)


def percentiles(values):
    """Midrank, endpoints 0/100, tied values equal. Singleton neutral 50."""
    n = len(values)
    if n < 2:
        return {key: 50.0 for key in values}
    ordered = sorted(values.values())
    return {key: 100 * (sum(v < value for v in ordered) + (sum(v == value for v in ordered) - 1) / 2) / (n - 1)
            for key, value in values.items()}


def join_window(base, advanced, opponent, expected_ids):
    """Require matching tables; absent teams stay absent, never become zero."""
    if not (base.keys() == advanced.keys() == opponent.keys()):
        raise ValueError("Base/Advanced/Opponent team coverage differs")
    if not set(base).issubset(expected_ids):
        raise ValueError("Unexpected team ID")
    rows = {}
    for team_id in base:
        b, a, o = base[team_id], advanced[team_id], opponent[team_id]
        gp = number(b, "GP")
        if gp != number(a, "GP") or gp != number(o, "GP"):
            raise ValueError(f"Game counts differ for {team_id}")
        if gp == 0:
            continue
        dreb = number(a, "DREB_PCT", hi=1)
        rows[team_id] = dict(team_id=team_id, team=b["TEAM_NAME"], gp=int(gp),
            three_volume=number(b, "FG3A"), shooting=number(b, "FG3_PCT", hi=1),
            oreb=number(a, "OREB_PCT", hi=1),
            perimeter_vulnerability=number(o, "OPP_FG3A"), dreb_weakness=1-dreb,
            pace=number(a, "PACE"), dreb_pct=dreb,
            possessions=number(a, "POSS"))
    complete = set(rows) == set(expected_ids) and len(expected_ids) == 30
    for metric in METRICS:
        ranks = percentiles({tid: r[metric] for tid, r in rows.items()}) if complete else {}
        for tid, row in rows.items():
            row[metric + "_pctile"] = ranks.get(tid)
    return rows, {"teams_with_games": len(rows), "league_percentiles_available": complete,
                  "min_gp": min((r["gp"] for r in rows.values()), default=0)}


def slate_from_schedule(payload, target, season):
    league = payload["leagueSchedule"]
    if league.get("seasonYear") != season:
        raise ValueError(f"Schedule season {league.get('seasonYear')} != {season}")
    teams, games, seen = {}, [], set()
    found_date = False
    for entry in league["gameDates"]:
        day = datetime.strptime(entry["gameDate"].split()[0], "%m/%d/%Y").date()
        for g in entry["games"]:
            for side in ("homeTeam", "awayTeam"):
                t = g[side]
                if int(t["teamId"]) in NBA_TEAM_IDS:
                    teams[int(t["teamId"])] = t["teamTricode"]
            if day != target:
                continue
            found_date = True
            # NBA game IDs 002 = regular season; exclude preseason/play-in/playoffs.
            if not str(g["gameId"]).startswith("002"):
                continue
            if g["gameId"] in seen:
                raise ValueError("Duplicate game in schedule")
            seen.add(g["gameId"])
            if any(int(g[side]["teamId"]) not in NBA_TEAM_IDS for side in ("homeTeam", "awayTeam")):
                raise ValueError("Unresolved team in regular-season slate")
            games.append({"game_id": g["gameId"], "away_id": int(g["awayTeam"]["teamId"]),
                          "home_id": int(g["homeTeam"]["teamId"]),
                          "status": g.get("gameStatusText", ""),
                          "game_status": g.get("gameStatus")})
    if len(teams) != 30:
        raise ValueError(f"Expected 30 NBA teams, got {len(teams)}")
    if not found_date:
        raise ValueError("Requested date absent from schedule; cannot verify empty slate")
    return teams, games


def matchup_rows(games, teams, window, stats):
    rows = []
    for game in games:
        for side, other in (("away_id", "home_id"), ("home_id", "away_id")):
            tid, oid = game[side], game[other]
            off, defense = stats.get(tid), stats.get(oid)
            row = dict(game_id=game["game_id"], window=window,
                       offense=teams[tid], opponent=teams[oid],
                       venue="Away" if side == "away_id" else "Home", status=game["status"],
                       offense_gp=off["gp"] if off else 0, opponent_gp=defense["gp"] if defense else 0)
            for metric in METRICS:
                source = defense if metric in ("perimeter_vulnerability", "dreb_weakness") else off
                row[metric + "_pctile"] = source.get(metric + "_pctile") if source else None
            row["opponent_pace_pctile"] = defense.get("pace_pctile") if defense else None
            row.update(
                own_three_pa_per100=off["three_volume"] if off else None,
                own_three_pct=off["shooting"] if off else None,
                opponent_three_pa_allowed_per100=defense["perimeter_vulnerability"] if defense else None,
                own_pace=off["pace"] if off else None,
                opponent_pace=defense["pace"] if defense else None,
            )
            # A transparent opportunity illustration, not a fitted forecast or qualification score.
            possessions = (off["pace"] + defense["pace"]) / 2 if off and defense else None
            attempts = ((off["three_volume"] + defense["perimeter_vulnerability"]) / 2
                        * possessions / 100) if possessions is not None else None
            baseline = off["three_volume"] * off["pace"] / 100 if off else None
            row.update(illustrative_game_possessions=possessions,
                       illustrative_three_pa=attempts,
                       own_baseline_three_pa=baseline,
                       illustrative_three_pa_change=attempts-baseline if attempts is not None else None)
            row["sample_note"] = ("Prior-season context; verify roster/role changes" if window == "prior_season"
                                  else "Thin sample (<10 games)" if min(row["offense_gp"], row["opponent_gp"]) < 10
                                  else "Descriptive team environment; player check required")
            rows.append(row)
    # Retain schedule order and both directions. An unweighted metric count is not our method.
    return rows


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value):
    return "—" if value is None else str(round(value))


def report(day, cutoff, season, recent, windows, health, matches):
    lines = [f"# BBB triples environments — {day.isoformat()}", "",
        f"Regular season only. Results through {cutoff.isoformat()}; excludes all games on the slate date.", "",
        "Higher percentiles always favor the offense's three-point environment. These are league ranks, not hit probabilities.", "",
        "This is a team watchlist, not a player prop recommendation. Injuries, rotations, and shot-location matchups have not been reviewed.", "",
        "Schedule order only; no automatic qualification score. Pass 1 pairs offensive volume and accuracy with opponent attempt concessions. Apply METHOD.md and assess shot quality separately in Pass 2.", ""]
    lines.insert(2, grounded_header())
    for window, label in (("current_season", "Current season"), ("recent", f"Recent: last {recent} games"), ("prior_season", "Prior-season baseline")):
        h = health[window]
        lines += [f"## {label}", "", f"Season {windows[window]['season']}; teams with games: {h['teams_with_games']}/30; minimum GP: {h['min_gp']}.", ""]
        if not h["league_percentiles_available"]:
            lines += ["League percentiles withheld: all 30 teams must have games in the window. See raw team rates below or in team_windows.csv.", ""]
        lines += ["| Offense vs defense | GP O/D | Own 3PA/100 (P) | Own 3P% (P) | Opp 3PA allowed/100 (P) | Pace O/D | Approx. possessions | Approx. 3PA / own baseline |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for row in matches[window]:
            rate = lambda v: "—" if v is None else f"{v:.1f}"
            pct = lambda v: "—" if v is None else f"{v:.1%}"
            lines.append(f"| {row['offense']} vs {row['opponent']} ({row['venue']}) | {row['offense_gp']}/{row['opponent_gp']} | "
                         f"{rate(row['own_three_pa_per100'])} (P{fmt(row['three_volume_pctile'])}) | "
                         f"{pct(row['own_three_pct'])} (P{fmt(row['shooting_pctile'])}) | "
                         f"{rate(row['opponent_three_pa_allowed_per100'])} (P{fmt(row['perimeter_vulnerability_pctile'])}) | "
                         f"{rate(row['own_pace'])}/{rate(row['opponent_pace'])} | {rate(row['illustrative_game_possessions'])} | "
                         f"{rate(row['illustrative_three_pa'])}/{rate(row['own_baseline_three_pa'])} |")
        lines += ["", "Opportunity illustration: mean team pace × mean(own 3PA/100, opponent allowed 3PA/100) / 100. Own baseline uses own pace and attempt rate. This is not a fitted forecast, a makes projection or a second pace bonus. Missing percentile = unavailable league coverage.", ""]
        if window != "prior_season":
            if h["min_gp"] < 10:
                lines += ["Thin sample: fewer than 10 games for at least one reporting team. Recent and season windows overlap; they are not independent confirmations.", ""]
    lines += ["## Interpretation", "", "Prior-season rankings describe the old roster and coaching context. They are shown separately, never silently blended into this season.", "",
        "Opponent 3PA allowed is a volume-concession measure, not a complete measure of perimeter defense. Shooting is observed team 3P%, not a roster-adjusted talent estimate.", "",
        "OREB and weak opponent DREB indicate support. The association layer below separately measures reconstructed next-shot links and NBA-tagged second-chance threes; it does not label all of them direct kick-outs.", "",
        "No pace or rebounding bonus is added to a projection. There is no makes projection in v1, avoiding double-counting opportunities already present in 3PA/100.", "",
        "All raw responses, exact request URLs, timestamps, and reuse flags are preserved in raw/ and run_manifest.json. No sportsbook or outside pricing feed is used.", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=datetime.now(ZoneInfo("America/Chicago")).date().isoformat())
    parser.add_argument("--recent", type=int, default=10)
    parser.add_argument("--out", type=Path, default=Path("bbb_output"))
    parser.add_argument("--offline", action="store_true", help="Replay exact-request cached responses only")
    parser.add_argument("--skip-connections", action="store_true", help="Explicit core-only diagnostic run")
    args = parser.parse_args(argv)
    day = date.fromisoformat(args.date)
    if args.recent < 1:
        parser.error("--recent must be positive")
    season, cutoff = season_for(day), day-timedelta(days=1)
    args.out.mkdir(parents=True, exist_ok=True)
    raw_dir, sources = args.out / "raw", []
    payload, source = get_json(SCHEDULE_URL, raw_dir, args.offline)
    schedule = payload
    sources.append(source)
    teams, games = slate_from_schedule(payload, day, season)
    prior = previous_season(season)
    definitions = [("prior_season", prior, date(int(season[:4]), 6, 30), 0),
                   ("current_season", season, cutoff, 0), ("recent", season, cutoff, args.recent)]
    windows, health, matches, team_rows = {}, {}, {}, []
    for window, window_season, window_cutoff, last_n in definitions:
        tables = []
        for measure in ("Base", "Advanced", "Opponent"):
            payload, source = get_json(stats_url(window_season, window_cutoff, last_n, measure), raw_dir, args.offline)
            params = payload.get("parameters", {})
            if params.get("Season") != window_season or params.get("MeasureType") != measure or params.get("PerMode") != "Per100Possessions":
                raise ValueError("Response parameters differ from requested window/measure")
            if str(params.get("DateTo", "")) != window_cutoff.strftime("%m/%d/%Y") or int(params.get("LastNGames", -1)) != last_n or params.get("SeasonType") != "Regular Season":
                raise ValueError("Response date/window/type differs from request")
            sources.append(source)
            tables.append(unpack(payload))
        rows, info = join_window(*tables, set(teams))
        for tid, row in rows.items():
            row.update(window=window, season=window_season, through=window_cutoff.isoformat(), abbreviation=teams[tid])
            team_rows.append(row)
        windows[window] = {"season": window_season, "rows": rows}
        health[window] = info
        matches[window] = matchup_rows(games, teams, window, rows)
    text = report(day, cutoff, season, args.recent, windows, health, matches)
    connection_summary = {"enabled": not args.skip_connections}
    if not args.skip_connections:
        from bbb_connections import build_connections, render_connections
        result = build_connections(schedule, cutoff, args.recent, windows, teams, raw_dir,
                                   get_json, args.offline, percentiles)
        text += "\n" + render_connections(result, games, teams)
        for name, data in (("connection_team_windows", result["rows"]),
                           ("rebound_event_audit", result["audit"]),
                           ("three_event_audit", result["threes"]),
                           ("rebound_shooter_pairs", result["player_pairs"]),
                           ("assist_shooter_pairs", result["assist_pairs"]),
                           ("player_three_opportunities", result["shooter_rows"]),
                           ("connection_validation", result["validations"])):
            write_csv(args.out / (name + ".csv"), data)
        (args.out / "connection_errors.json").write_text(json.dumps(result["errors"], indent=2))
        sources.extend(result["sources"])
        connection_summary.update(expected_games=result["expected_games"], validated_games=result["validated_games"],
                                  errors=result["errors"], analysis_status="Descriptive inputs only; apply canonical method before qualification")
    else:
        text += "\nAssociation and assist layers explicitly disabled for this diagnostic run.\n"
    write_csv(args.out / "team_windows.csv", team_rows)
    write_csv(args.out / "matchups.csv", [r for window in matches.values() for r in window])
    (args.out / "report.md").write_text(text)
    manifest = {"version": VERSION, "slate_date": day.isoformat(), "cutoff": cutoff.isoformat(),
                "generated_at": datetime.now(timezone.utc).isoformat(), "recent_games": args.recent,
                "method": metadata(),
                "health": health, "games": games, "connections": connection_summary, "sources": sources}
    (args.out / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
