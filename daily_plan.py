#!/usr/bin/env python3
"""Plan a Chicago NBA slate; emit JSON only. No scheduler or Sheets writer."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from bbb_triples import HEADERS, NBA_TEAM_IDS, SCHEDULE_URL, season_for

CHICAGO = ZoneInfo("America/Chicago")
EASTERN = ZoneInfo("America/New_York")
UTC = timezone.utc
ROLE_CONTROLS = {
    "Admin": ("gpt-6.1-sol", "medium"),
    "Codex": ("gpt-6.1-sol", "medium"),
    "Supervisor": ("gpt-6.1-sol", "high"),
    "Bridge": ("gpt-6-luna", "low"),
}


def strict_json(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError(f"Duplicate JSON key: {key}")
            obj[key] = value
        return obj

    def invalid(value):
        raise ValueError(f"Invalid JSON number: {value}")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)


def validate_profiles(config):
    """Reject substitutions; accepted requested controls are not runtime proof."""
    if not isinstance(config, dict) or set(config) != {"schema_version", "roles", "creates_scheduler", "creates_sheet_writer"}:
        raise ValueError("Invalid role config fields")
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValueError("Unsupported role config version")
    if config["creates_scheduler"] is not False or config["creates_sheet_writer"] is not False:
        raise ValueError("These files create no scheduler or Sheets writer")
    roles = config["roles"]
    if not isinstance(roles, dict) or set(roles) != set(ROLE_CONTROLS):
        raise ValueError("Exactly Admin, Codex, Supervisor and Bridge required")
    for role, (model, effort) in ROLE_CONTROLS.items():
        expected = dict(model=model, reasoning_effort=effort, fork_turns="none")
        if roles[role] != expected:
            raise ValueError(f"Role controls differ for {role}; silent substitution forbidden")
    return roles


def iso_date(text):
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError("Slate date must be explicit YYYY-MM-DD")
    return date.fromisoformat(text)


def utc_stamp(text):
    if not isinstance(text, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", text):
        raise ValueError("Expected aware UTC ISO timestamp")
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return value.astimezone(UTC)


def load_schedule(path=None, *, label=None):
    """Read an official payload/envelope, or fetch only the fixed official URL."""
    source = dict(url=SCHEDULE_URL, mode="file" if path else "fetch", label=label,
                  read_at=None, fetched_at=None)
    if path:
        raw = Path(path).read_bytes()
        source.update(file=str(path), read_at=datetime.now(UTC).isoformat())
    else:
        request = urllib.request.Request(SCHEDULE_URL, headers=HEADERS)
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.geturl() != SCHEDULE_URL:
                raise ValueError("Unexpected schedule redirect")
            raw = response.read()
        source["fetched_at"] = datetime.now(UTC).isoformat()
    source["input_sha256"] = hashlib.sha256(raw).hexdigest()
    payload = strict_json(raw)
    if isinstance(payload, dict) and "payload" in payload:
        if not path or payload.get("url") != SCHEDULE_URL:
            raise ValueError("Saved envelope URL must match official schedule exactly")
        utc_stamp(payload.get("fetched_at"))
        source["fetched_at"] = payload["fetched_at"]
        source["mode"] = "saved_envelope"
        payload = payload["payload"]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode("utf-8")
    source["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    source["payload_hash_format"] = "UTF-8 JSON, sorted keys, compact, ensure_ascii=False"
    return payload, source


def build_plan(payload, target, source=None):
    """Conservative scheduleLeagueV2_1 validation; errors never expose an exact plan."""
    result = dict(schema_version=1, state="error", slate_date=target, timezone="America/Chicago",
                  results_cutoff=None, first_tip_at=None, launch_at=None,
                  eligible_game_ids=[], excluded_games=[], unresolved_game_ids=[],
                  source=source, errors=[])
    try:
        day = iso_date(target)
        result["results_cutoff"] = (day - timedelta(days=1)).isoformat()
        _schedule(payload, day, result)
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        result["state"] = "error"
        result["first_tip_at"] = result["launch_at"] = None
        result["errors"].append(str(exc))
    return result


def _schedule(payload, day, result):
    if not isinstance(payload, dict) or not isinstance(payload.get("leagueSchedule"), dict):
        raise ValueError("Missing leagueSchedule object")
    league = payload["leagueSchedule"]
    if league.get("leagueId") != "00" or league.get("seasonYear") != season_for(day):
        raise ValueError("Wrong league or season for slate date")
    entries = league.get("gameDates")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Missing/non-list/empty gameDates")
    dates, ids, tips = set(), set(), []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Invalid gameDates entry")
        raw_day = entry.get("gameDate")
        if not isinstance(raw_day, str) or not re.fullmatch(r"\d{2}/\d{2}/\d{4} 00:00:00", raw_day):
            raise ValueError("Invalid schedule gameDate")
        nominal = datetime.strptime(raw_day, "%m/%d/%Y %H:%M:%S").date()
        if nominal in dates or season_for(nominal) != league["seasonYear"]:
            raise ValueError("Duplicate schedule date or date outside season")
        dates.add(nominal)
        games = entry.get("games")
        if not isinstance(games, list):
            raise ValueError("Missing/non-list games")
        for game in games:
            if not isinstance(game, dict):
                raise ValueError("Invalid game object")
            gid = game.get("gameId")
            if not isinstance(gid, str) or not re.fullmatch(r"00[1-6]\d{7}", gid):
                raise ValueError("Invalid/unknown NBA game ID phase")
            if gid in ids or gid[3:5] != league["seasonYear"][2:4] or int(gid[5:]) == 0:
                raise ValueError(f"Duplicate/wrong-season game ID: {gid}")
            ids.add(gid)
            # Same explicit regular-season ID family used by bbb_triples. Cup
            # group/knockout 002 games count; cup final 006 does not. Labels do not decide.
            if not gid.startswith("002"):
                continue
            _game(game, nominal, day, result, tips)
    if result["unresolved_game_ids"]:
        raise ValueError("Potentially relevant games have unresolved times/teams")
    if not tips:
        if day not in dates:
            raise ValueError("Slate date absent; cannot verify no-games state")
        result["state"] = "no_games"
        return
    first = min(tips)
    result.update(state="ready", first_tip_at=first.astimezone(CHICAGO).isoformat(),
                  launch_at=(first - timedelta(minutes=120)).astimezone(CHICAGO).isoformat())


def _game(game, nominal, day, result, tips):
    gid = game["gameId"]
    status = game.get("gameStatus")
    if type(status) is not int or status not in (1, 2, 3):
        raise ValueError(f"Unknown gameStatus for {gid}")
    text = game.get("gameStatusText")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Missing gameStatusText for {gid}")
    text = text.strip().casefold()
    postponed = game.get("postponedStatus")
    if postponed not in ("N", "Y"):
        raise ValueError(f"Unknown postponedStatus for {gid}")
    cancelled = text in ("canceled", "cancelled")
    inactive = cancelled or postponed == "Y" or text in ("ppd", "postponed")
    if inactive and status != 1:
        raise ValueError(f"Conflicting inactive/live-final status for {gid}")
    nominal_stamp = game.get("gameDateEst")
    if nominal_stamp != nominal.isoformat() + "T00:00:00Z":
        raise ValueError(f"gameDateEst/entry mismatch for {gid}")
    code = game.get("gameCode")
    if not isinstance(code, str) or (code and not re.fullmatch(
            nominal.strftime("%Y%m%d") + r"/[A-Z]{6}", code)):
        raise ValueError(f"Invalid gameCode/date for {gid}")
    tbd_flag = game.get("gameTimeTBD", False)
    if type(tbd_flag) is not bool:
        raise ValueError(f"Invalid gameTimeTBD flag for {gid}")
    raw_tip = game.get("gameDateTimeUTC")
    tip = utc_stamp(raw_tip) if raw_tip not in (None, "") else None
    if tip and tip.astimezone(EASTERN).date() != nominal:
        raise ValueError(f"UTC tip/nominal Eastern date mismatch for {gid}")
    unresolved = tbd_flag or text in ("tbd", "tba", "time tbd") or tip is None
    if not inactive:
        if status == 1 and not (unresolved or text == "scheduled" or re.fullmatch(
                r"(?:[1-9]|1[0-2]):[0-5][0-9] [ap]m et", text)):
            raise ValueError(f"Unknown scheduled status text for {gid}")
        if status == 3 and not re.fullmatch(r"final(?:/ot\d*)?", text):
            raise ValueError(f"Conflicting final status text for {gid}")
        if status == 2 and not (text in ("halftime", "half time") or re.fullmatch(
                r"(?:end of )?(?:q[1-4]|[1-4](?:st|nd|rd|th)(?: qtr)?|ot\d*|\d+ot)(?: \d{1,2}:[0-5]\d(?:\.\d+)?)?", text)):
            raise ValueError(f"Unknown/conflicting live status text for {gid}")
        if status == 1 and tip and not unresolved and re.fullmatch(
                r"(?:[1-9]|1[0-2]):[0-5][0-9] [ap]m et", text):
            displayed = datetime.strptime(text[:-3], "%I:%M %p")
            eastern = tip.astimezone(EASTERN)
            if (displayed.hour, displayed.minute) != (eastern.hour, eastern.minute):
                raise ValueError(f"Displayed status time/UTC tip mismatch for {gid}")
    # A TBD Eastern-date game might fall on that Chicago date OR the preceding
    # Chicago date. Never trust its placeholder midnight UTC time to exclude it.
    relevant = nominal in (day, day + timedelta(days=1)) if unresolved else tip.astimezone(CHICAGO).date() == day
    if not relevant:
        return
    if inactive:
        result["excluded_games"].append(dict(game_id=gid, reason="cancelled" if cancelled else "postponed"))
        return
    home, away = game.get("homeTeam"), game.get("awayTeam")
    team_ids = [t.get("teamId") if isinstance(t, dict) else None for t in (home, away)]
    valid_teams = all(type(t) is int and t in NBA_TEAM_IDS for t in team_ids)
    if valid_teams and team_ids[0] == team_ids[1]:
        raise ValueError(f"Same team on both sides for {gid}")
    if unresolved or not valid_teams or not code:
        result["unresolved_game_ids"].append(gid)
        return
    if code[-6:] != away.get("teamTricode", "") + home.get("teamTricode", ""):
        raise ValueError(f"gameCode/team identity mismatch for {gid}")
    result["eligible_game_ids"].append(gid)
    tips.append(tip)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Explicit Chicago slate YYYY-MM-DD")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--schedule-json", type=Path, help="Saved official payload or exact-URL cache envelope")
    source.add_argument("--fetch", action="store_true", help="Fetch fixed official schedule using NBA headers")
    parser.add_argument("--source-label", help="E.g. Root-fetched snapshot; never relabel an offline read live")
    parser.add_argument("--profiles", type=Path, default=Path(__file__).with_name("daily_roles.json"))
    args = parser.parse_args(argv)
    try:
        iso_date(args.date)
        validate_profiles(strict_json(args.profiles.read_bytes()))
        payload, provenance = load_schedule(args.schedule_json, label=args.source_label)
        result = build_plan(payload, args.date, provenance)
    except (OSError, ValueError, TypeError) as exc:
        result = dict(state="error", slate_date=args.date, timezone="America/Chicago",
                      first_tip_at=None, launch_at=None, errors=[str(exc)])
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 2 if result["state"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
