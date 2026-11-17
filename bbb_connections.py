"""Event-audited rebound-to-three links and secondary assisted-three context.

No pass is inferred for a missed shot. NBA's second-chance qualifier is kept
separate from the narrower, explicitly reconstructed next-shot association.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

LINK_METRICS = ("oreb_next3_rate", "opp_oreb_next3_rate", "second_chance_3pa_per100",
                "opp_second_chance_3pa_per100", "assisted_3pm_per100", "opp_assisted_3pm_per100")


def seconds(clock):
    m = re.fullmatch(r"PT(\d+)M([\d.]+)S", clock)
    if not m:
        raise ValueError(f"Unrecognized game clock: {clock}")
    return int(m[1]) * 60 + float(m[2])


def parse_game(pbp, box, expected_game):
    """Reconstruct personal-OREB -> next FGA, stopping at FT trips/changes.

    A personal recovery is an anchor. Its first subsequent FGA can link even
    on a miss. Later OREBs start new anchors. This is association, not a pass.
    Team rebounds are not personal anchors. No reconstructed possession totals
    are used; the broader second-chance category comes from NBA qualifiers.
    """
    game, score = pbp["game"], box["game"]
    if str(game["gameId"]) != str(expected_game) or str(score["gameId"]) != str(expected_game):
        raise ValueError("Game identity mismatch")
    if score["gameStatus"] != 3:
        raise ValueError("Boxscore is not final")
    ids = {int(score[s]["teamId"]) for s in ("homeTeam", "awayTeam")}
    if len(ids) != 2:
        raise ValueError("Expected two distinct teams")
    opponent = {tid: next(x for x in ids if x != tid) for tid in ids}
    actions = game["actions"]
    if len({a["actionNumber"] for a in actions}) != len(actions):
        raise ValueError("Duplicate action IDs")
    # orderNumber is the corrected order within a period; actionNumber can be out of order.
    actions = sorted(actions, key=lambda a: (int(a["period"]), float(a["orderNumber"])))
    by_action = {a["actionNumber"]: a for a in actions}
    totals = {tid: Counter() for tid in ids}
    audits, threes, pending, period = [], [], None, None
    def close(reason):
        nonlocal pending
        if pending is not None:
            pending["outcome"] = reason
            audits.append(pending)
            pending = None
    for a in actions:
        typ, sub = a["actionType"].lower(), str(a.get("subType", "")).lower()
        tid, pid = a.get("teamId"), a.get("personId")
        if a["period"] != period:
            close("period_end")
            period = a["period"]
        # Non-playing events (substitutions/timeouts/fouls) can name the other
        # team without changing possession. Only ball-control events reset it.
        if typ in ("period", "game"):
            close("period_or_game_end")
            continue
        is_shot = typ in ("2pt", "3pt") and bool(a.get("isFieldGoal"))
        if is_shot:
            if tid not in ids or not pid or a.get("shotResult") not in ("Made", "Missed"):
                raise ValueError("Invalid field-goal event")
            made = a["shotResult"] == "Made"
            assisted = made and bool(a.get("assistPersonId"))
            totals[tid]["fga"] += 1
            totals[tid]["fgm"] += made
            totals[tid]["assists"] += assisted
            second = "2ndchance" in a.get("qualifiers", [])
            if second:
                totals[tid]["source_second_fga"] += 1
                totals[tid]["source_second_fgm"] += made
            linked_anchor = None
            if pending is not None:
                if pending["team_id"] == tid:
                    elapsed = round(seconds(pending["rebound_clock"]) - seconds(a["clock"]), 3)
                    if elapsed < 0:
                        raise ValueError("Shot occurs before rebound")
                    pending.update(shot_action=a["actionNumber"], shooter_id=pid,
                                   shooter=a.get("playerNameI", a.get("playerName", str(pid))),
                                   shot_type=typ, made=made, elapsed_seconds=elapsed,
                                   source_second_chance=second,
                                   assister_id=a.get("assistPersonId") if assisted else None)
                    # Reconstruct the sequence from ordered play-by-play. The
                    # separate NBA qualifier is a cross-check, not a veto on
                    # a valid rebound/next-shot relationship or a team window.
                    if not second:
                        totals[tid]["untagged_next_fga"] += 1
                        totals[tid]["untagged_next3"] += typ == "3pt"
                    linked_anchor = pending["rebound_action"]
                    totals[tid]["oreb_next_fga"] += 1
                    totals[tid]["oreb_next3"] += typ == "3pt"
                    close("next_3pa" if typ == "3pt" else "next_2pa")
                else:
                    close("opponent_field_goal_attempt")
            if typ == "3pt":
                totals[tid]["three_pa"] += 1
                totals[tid]["three_pm"] += made
                totals[tid]["assisted_three_pm"] += assisted
                totals[tid]["source_second_three_pa"] += second
                threes.append(dict(game_id=str(expected_game), team_id=tid, opponent_id=opponent[tid],
                    action=a["actionNumber"], period=a["period"], clock=a["clock"], shooter_id=pid,
                    shooter=a.get("playerNameI", a.get("playerName", str(pid))), made=made,
                    source_second_chance=second, linked_rebound_action=linked_anchor,
                    assister_id=a.get("assistPersonId") if assisted else None,
                    assister=a.get("assistPlayerNameInitial", "") if assisted else "",
                    passer_on_miss="unavailable" if not made else "not_applicable"))
            continue
        if typ == "rebound":
            if tid not in ids:
                raise ValueError("Rebound has invalid team")
            if sub == "defensive":
                close("defensive_rebound")
                continue
            if sub != "offensive":
                raise ValueError("Unknown rebound subtype")
            if not pid:
                # Dead-ball/team rebound is not a live player recovery. Avoid
                # bridging an earlier anchor through uncertain team possession.
                close("team_rebound_boundary")
                continue
            close("another_offensive_rebound")
            totals[tid]["personal_oreb"] += 1
            missed = by_action.get(a.get("shotActionNumber"))
            if not missed or missed.get("teamId") != tid or missed.get("shotResult") != "Missed":
                raise ValueError("Personal OREB lacks a same-team missed-shot reference")
            if missed["actionType"] == "freethrow":
                ft = re.fullmatch(r"(\d+) of (\d+)", missed.get("subType", ""))
                if not ft or ft[1] != ft[2]:
                    raise ValueError("Personal OREB after non-final/unknown free throw")
            elif missed["actionType"] not in ("2pt", "3pt"):
                raise ValueError("OREB references a non-shot")
            pending = dict(game_id=str(expected_game), team_id=tid, opponent_id=opponent[tid],
                rebound_action=a["actionNumber"], period=a["period"], rebound_clock=a["clock"],
                rebounder_id=pid, rebounder=a.get("playerNameI", a.get("playerName", str(pid))),
                missed_shot_action=missed["actionNumber"], shot_action=None, shooter_id=None,
                shooter="", shot_type="", made=None, elapsed_seconds=None,
                source_second_chance=None, assister_id=None, outcome="")
        elif typ in ("turnover", "jumpball"):
            close(typ)
        elif typ == "foul" and "offensive" in sub:
            close("offensive_foul")
        elif typ == "freethrow":
            # Technical FT does not necessarily terminate the original possession.
            description = str(a.get("description", "")).lower()
            if "technical" not in description and "technical" not in sub:
                close("free_throw_trip")
    close("end_of_feed")
    validations = []
    for side in ("homeTeam", "awayTeam"):
        team = score[side]
        tid, stats = int(team["teamId"]), team["statistics"]
        mapping = {"fga":"fieldGoalsAttempted", "fgm":"fieldGoalsMade", "three_pa":"threePointersAttempted",
                   "three_pm":"threePointersMade", "personal_oreb":"reboundsOffensive", "assists":"assists",
                   "source_second_fga":"secondChancePointsAttempted", "source_second_fgm":"secondChancePointsMade"}
        for key, source in mapping.items():
            actual, expected = totals[tid][key], stats[source]
            if actual != expected:
                raise ValueError(f"{team['teamTricode']} {key}: PBP {actual} != box {expected}")
            validations.append(dict(game_id=str(expected_game), team_id=tid, check=key, pbp=actual, boxscore=expected))
        totals[tid]["opponent_id"] = opponent[tid]
    return {"game_id": str(expected_game), "totals": totals, "audit": audits,
            "threes": threes, "validations": validations}


def completed_games(schedule, cutoff):
    games, seen = [], set()
    for day in schedule["leagueSchedule"]["gameDates"]:
        dt = datetime.strptime(day["gameDate"].split()[0], "%m/%d/%Y").date()
        if dt > cutoff:
            continue
        for g in day["games"]:
            if not str(g["gameId"]).startswith("002") or g.get("gameStatus") != 3:
                continue
            if g["gameId"] in seen:
                raise ValueError("Duplicate completed game")
            seen.add(g["gameId"])
            games.append(dict(game_id=g["gameId"], date=dt.isoformat(),
                              home_id=int(g["homeTeam"]["teamId"]), away_id=int(g["awayTeam"]["teamId"])))
    return sorted(games, key=lambda g: (g["date"], g["game_id"]))


def build_connections(schedule, cutoff, recent, windows, teams, raw_dir, get_json, offline, ranker):
    expected = completed_games(schedule, cutoff)
    def load(g):
        sources = []
        try:
            payloads = []
            for kind in ("playbyplay", "boxscore"):
                url = f"https://cdn.nba.com/static/json/liveData/{kind}/{kind}_{g['game_id']}.json"
                # Final event feeds are reused incrementally. Delete their exact
                # raw files to force a correction refresh. No failed-fetch fallback.
                cache = raw_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")
                p, source = get_json(url, raw_dir, offline=offline or cache.exists())
                sources.append(source)
                payloads.append(p)
            parsed = parse_game(*payloads, g["game_id"])
            if set(parsed["totals"]) != {g["home_id"], g["away_id"]}:
                raise ValueError("Schedule/PBP teams differ")
            return g, parsed, sources, None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return g, None, sources, f"{type(exc).__name__}: {exc}"
    with ThreadPoolExecutor(max_workers=4) as pool:
        loaded = list(pool.map(load, expected))
    parsed = {g["game_id"]: p for g, p, _, err in loaded if not err}
    sources = [s for _, _, ss, _ in loaded for s in ss]
    errors = [dict(game_id=g["game_id"], error=err) for g, _, _, err in loaded if err]
    all_rows, output = [], {}
    for window in ("current_season", "recent"):
        rows = {}
        for tid in teams:
            own_games = [g for g in expected if tid in (g["home_id"], g["away_id"])]
            if window == "recent":
                own_games = own_games[-recent:]
            core = windows[window]["rows"].get(tid)
            required_gp = core["gp"] if core else 0
            valid = required_gp > 0 and len(own_games) == required_gp and all(g["game_id"] in parsed for g in own_games)
            own, opp = Counter(), Counter()
            for g in own_games:
                p = parsed.get(g["game_id"])
                if p:
                    mine = p["totals"][tid]
                    own.update({k:v for k,v in mine.items() if k != "opponent_id"})
                    opp.update({k:v for k,v in p["totals"][mine["opponent_id"]].items() if k != "opponent_id"})
            # Missing qualifier tags do not erase reconstructed associations.
            # Actual game/coverage validation failures still suppress rates.
            association_valid = valid
            poss = core.get("possessions", 0) if core else 0
            row = dict(window=window, team_id=tid, team=teams[tid], gp=required_gp,
                games_validated=sum(g["game_id"] in parsed for g in own_games),
                coverage_complete=valid, association_complete=association_valid,
                next_fga_without_tag=own["untagged_next_fga"] if valid else None,
                next3_without_tag=own["untagged_next3"] if valid else None,
                opponent_next_fga_without_tag=opp["untagged_next_fga"] if valid else None,
                opponent_next3_without_tag=opp["untagged_next3"] if valid else None,
                personal_oreb=own["personal_oreb"] if valid else None,
                next3_after_oreb=own["oreb_next3"] if association_valid else None,
                opponent_personal_oreb=opp["personal_oreb"] if valid else None,
                opponent_next3_after_oreb=opp["oreb_next3"] if association_valid else None,
                source_second_chance_3pa=own["source_second_three_pa"] if valid else None,
                assisted_3pm=own["assisted_three_pm"] if valid else None,
                opponent_assisted_3pm=opp["assisted_three_pm"] if valid else None,
                possessions=poss if valid else None,
                oreb_next3_rate=own["oreb_next3"]/own["personal_oreb"] if association_valid and own["personal_oreb"] else None,
                opp_oreb_next3_rate=opp["oreb_next3"]/opp["personal_oreb"] if association_valid and opp["personal_oreb"] else None,
                second_chance_3pa_per100=100*own["source_second_three_pa"]/poss if valid and poss else None,
                opp_second_chance_3pa_per100=100*opp["source_second_three_pa"]/poss if valid and poss else None,
                assisted_3pm_per100=100*own["assisted_three_pm"]/poss if valid and poss else None,
                opp_assisted_3pm_per100=100*opp["assisted_three_pm"]/poss if valid and poss else None,
                note="Research only; wait for several weeks of current-season data")
            rows[tid] = row
        for metric in LINK_METRICS:
            values = {tid:r[metric] for tid,r in rows.items() if r[metric] is not None}
            # Never call a partial league sample a full league percentile.
            ranks = ranker(values) if len(values) == 30 else {}
            for tid, row in rows.items():
                row[metric+"_pctile"] = ranks.get(tid)
        output[window] = rows
        all_rows.extend(rows.values())
    audits = [r for p in parsed.values() for r in p["audit"]]
    threes = [r for p in parsed.values() for r in p["threes"]]
    validations = [r for p in parsed.values() for r in p["validations"]]
    # Raw player links: no player percentiles or role projections from tiny samples.
    pairs = defaultdict(lambda: Counter())
    for a in audits:
        if a["outcome"] == "next_3pa":
            key = (a["team_id"], a["rebounder_id"], a["rebounder"], a["shooter_id"], a["shooter"])
            pairs[key]["next_3pa"] += 1
            pairs[key]["next_3pm"] += bool(a["made"])
            pairs[key]["elapsed_seconds_total"] += a["elapsed_seconds"]
            pairs[key]["same_player_rebound_and_shot"] += a["rebounder_id"] == a["shooter_id"]
    player_pairs = [dict(team=teams[k[0]], team_id=k[0], rebounder_id=k[1], rebounder=k[2],
        shooter_id=k[3], shooter=k[4], **v,
        average_seconds=v["elapsed_seconds_total"]/v["next_3pa"],
        relationship="Sequence association; direct pass unobserved on misses") for k,v in pairs.items()]
    assists = defaultdict(lambda: Counter())
    for a in threes:
        if a["made"] and a["assister_id"]:
            key=(a["team_id"], a["assister_id"], a["assister"], a["shooter_id"], a["shooter"])
            assists[key]["assisted_3pm"] += 1
            assists[key]["second_chance_assisted_3pm"] += a["source_second_chance"]
    assist_pairs=[dict(team=teams[k[0]], team_id=k[0], assister_id=k[1], assister=k[2],
                       shooter_id=k[3], shooter=k[4], **v) for k,v in assists.items()]
    shooter_counts = defaultdict(Counter)
    team_links = Counter()
    for a in threes:
        key = (a["team_id"], a["shooter_id"], a["shooter"])
        linked = a["linked_rebound_action"] is not None
        shooter_counts[key]["three_pa"] += 1
        shooter_counts[key]["three_pm"] += a["made"]
        shooter_counts[key]["second_chance_three_pa"] += a["source_second_chance"]
        shooter_counts[key]["next_oreb_three_pa"] += linked
        shooter_counts[key]["assisted_three_pm"] += a["made"] and bool(a["assister_id"])
        team_links[a["team_id"]] += linked
    shooter_rows = [dict(team=teams[k[0]], team_id=k[0], shooter_id=k[1], shooter=k[2], **v,
        share_of_own_3pa_after_oreb=v["next_oreb_three_pa"]/v["three_pa"],
        share_of_team_oreb_next3=v["next_oreb_three_pa"]/team_links[k[0]] if team_links[k[0]] else None,
        scope="Validated current-season games only; inspect team coverage") for k,v in shooter_counts.items()]
    return dict(windows=output, rows=all_rows, audit=audits, threes=threes,
                player_pairs=player_pairs, assist_pairs=assist_pairs, shooter_rows=shooter_rows, validations=validations,
                sources=sources, errors=errors, expected_games=len(expected), validated_games=len(parsed))


def render_connections(result, games, teams):
    lines=["## Rebound-to-three associations and assisted-three context", "",
        f"Current-season completed games validated: {result['validated_games']}/{result['expected_games']}. Failed games: {len(result['errors'])}.", "",
        "Supporting context under METHOD.md: assists have provisional 5% influence and OREB at most 2.5%. These descriptive exports do not automatically change ordering or qualify a candidate.", "",
        "OREB link = a personal offensive rebound followed by the next field-goal attempt before a turnover, free-throw trip, team-rebound boundary, or period end. Misses count. NBA second-chance tags are audited separately; absent tags do not discard valid sequences. This is a sequence, not proof of a direct pass.", "",
        "Broader second-chance 3PA uses NBA's own 2ndchance qualifier and can include team rebounds. Assisted 3PM counts makes only; the passer on missed threes is unavailable. Both conceded rates use the defending team's own NBA possession denominator, matching its core per-100 convention.", ""]
    for window, label in (("current_season","Current season"),("recent","Recent games")):
        rows=result["windows"][window]
        fmt=lambda x: "—" if x is None else str(round(x))
        lines += [f"### {label}: matchup percentiles", "",
            "Higher favors the offense. Missing ranks mean league coverage or an eligible denominator is incomplete; missing is not zero.", "",
            "| Offense → opponent | OREB→3 rate | Opp OREB→3 conceded | 2nd-chance 3PA | Opp 2nd-chance 3PA | Assisted 3PM | Opp assisted 3PM |",
            "|---|---:|---:|---:|---:|---:|---:|"]
        for g in games:
            for tid,oid in ((g['away_id'],g['home_id']),(g['home_id'],g['away_id'])):
                o,d=rows[tid],rows[oid]
                values=[o['oreb_next3_rate_pctile'],d['opp_oreb_next3_rate_pctile'],
                        o['second_chance_3pa_per100_pctile'],d['opp_second_chance_3pa_per100_pctile'],
                        o['assisted_3pm_per100_pctile'],d['opp_assisted_3pm_per100_pctile']]
                lines.append(f"| {teams[tid]} → {teams[oid]} | "+" | ".join(map(fmt,values))+" |")
        lines += ["", "### Raw counts on the slate", "",
            "| Team | Validated/GP | Next 3PA / personal OREB | Opp next 3PA / OREB | NBA 2nd-chance 3PA | Assisted 3PM | Opp assisted 3PM |",
            "|---|---:|---:|---:|---:|---:|---:|"]
        for tid in sorted({g[k] for g in games for k in ('home_id','away_id')},key=lambda t:teams[t]):
            r=rows[tid]
            lines.append(f"| {teams[tid]} | {r['games_validated']}/{r['gp']} | {fmt(r['next3_after_oreb'])}/{fmt(r['personal_oreb'])} | {fmt(r['opponent_next3_after_oreb'])}/{fmt(r['opponent_personal_oreb'])} | {fmt(r['source_second_chance_3pa'])} | {fmt(r['assisted_3pm'])} | {fmt(r['opponent_assisted_3pm'])} |")
        lines += [""]
    lines += ["Team/window rates and counts: connection_team_windows.csv. Individual rebound/shooter links: rebound_shooter_pairs.csv. Made-three assist links: assist_shooter_pairs.csv. Every OREB boundary and outcome: rebound_event_audit.csv. Box-score reconciliation: connection_validation.csv. Failures: connection_errors.json.", ""]
    return "\n".join(lines)
