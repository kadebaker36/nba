"""Schedule safety, Chicago elapsed time and exact hosted role controls."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import daily_plan as p


def game(gid="0022600001", tip="2026-11-21T00:00:00Z", **changes):
    nominal = p.utc_stamp(tip).astimezone(p.EASTERN).date()
    value = dict(gameId=gid, gameStatus=1, gameStatusText="Scheduled", postponedStatus="N",
                 gameDateEst=nominal.isoformat()+"T00:00:00Z", gameDateTimeUTC=tip,
                 gameCode=nominal.strftime("%Y%m%d")+"/ATLBOS",
                 homeTeam=dict(teamId=1610612738, teamTricode="BOS"),
                 awayTeam=dict(teamId=1610612737, teamTricode="ATL"))
    value.update(changes)
    return value


def schedule(*games, empty_dates=(), season="2026-27"):
    by_date = {d: [] for d in empty_dates}
    for g in games:
        d = g["gameDateEst"][:10]
        by_date.setdefault(d, []).append(g)
    return dict(leagueSchedule=dict(leagueId="00", seasonYear=season,
        gameDates=[dict(gameDate=datetime.fromisoformat(d).strftime("%m/%d/%Y 00:00:00"), games=rows)
                   for d, rows in sorted(by_date.items())]))


class PlanTests(unittest.TestCase):
    def plan(self, payload=None, day="2026-11-20"):
        return p.build_plan(schedule(game()) if payload is None else payload, day)

    def error(self, payload, day="2026-11-20"):
        result = self.plan(payload, day)
        self.assertEqual(result["state"], "error", result)
        self.assertTrue(result["errors"])
        self.assertIsNone(result["first_tip_at"])
        self.assertIsNone(result["launch_at"])
        return result

    def test_multiple_games_and_utc_day_boundary(self):
        result = self.plan(schedule(game("0022600002", "2026-11-21T04:00:00Z"), game()))
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["first_tip_at"], "2026-11-20T18:00:00-06:00")
        self.assertEqual(result["launch_at"], "2026-11-20T16:00:00-06:00")
        self.assertEqual(result["results_cutoff"], "2026-11-19")
        self.assertEqual(result["eligible_game_ids"], ["0022600002", "0022600001"])

    def test_neighbor_eastern_date_included_by_chicago_day(self):
        result = self.plan(schedule(game(tip="2026-11-21T05:30:00Z")))
        self.assertEqual(result["first_tip_at"], "2026-11-20T23:30:00-06:00")
        result = self.plan(schedule(game(tip="2026-11-21T06:00:00Z"), empty_dates=("2026-11-20",)))
        self.assertEqual(result["state"], "no_games")

    def test_launch_previous_local_date(self):
        result = self.plan(schedule(game(tip="2026-11-20T06:30:00Z")))
        self.assertEqual(result["launch_at"], "2026-11-19T22:30:00-06:00")

    def test_spring_dst_elapsed_subtraction(self):
        result = self.plan(schedule(game(tip="2027-03-14T08:30:00Z")), "2027-03-14")
        self.assertEqual(result["first_tip_at"], "2027-03-14T03:30:00-05:00")
        self.assertEqual(result["launch_at"], "2027-03-14T00:30:00-06:00")
        self.assert_elapsed(result)

    def test_fall_dst_elapsed_subtraction(self):
        result = self.plan(schedule(game(tip="2026-11-01T08:30:00Z")), "2026-11-01")
        self.assertEqual(result["first_tip_at"], "2026-11-01T02:30:00-06:00")
        self.assertEqual(result["launch_at"], "2026-11-01T01:30:00-05:00")
        self.assert_elapsed(result)

    def assert_elapsed(self, result):
        first = datetime.fromisoformat(result["first_tip_at"]).astimezone(timezone.utc)
        launch = datetime.fromisoformat(result["launch_at"]).astimezone(timezone.utc)
        self.assertEqual(first-launch, timedelta(minutes=120))

    def test_explicit_empty_date_no_games_and_absent_date_error(self):
        self.assertEqual(self.plan(schedule(empty_dates=("2026-11-20",)))["state"], "no_games")
        self.error(schedule(empty_dates=("2026-11-19",)))
        self.error(schedule())

    def test_nonregular_phases_excluded_labels_do_not_decide(self):
        for phase in ("001", "003", "004", "005", "006"):
            with self.subTest(phase=phase):
                result = self.plan(schedule(game(gid=phase+"2600001", gameLabel="Regular Season")))
                self.assertEqual(result["state"], "no_games")
        result = self.plan(schedule(game(gameLabel="Emirates NBA Cup", gameSubtype="in-season-knockout")))
        self.assertEqual(result["state"], "ready")

    def test_cancelled_and_postponed_excluded(self):
        for changes, reason in ((dict(gameStatusText="Canceled"), "cancelled"),
                                (dict(gameStatusText="Cancelled"), "cancelled"),
                                (dict(gameStatusText="PPD"), "postponed"),
                                (dict(gameStatusText="Postponed"), "postponed"),
                                (dict(postponedStatus="Y", gameStatusText="TBD"), "postponed")):
            with self.subTest(changes=changes):
                result = self.plan(schedule(game(**changes)))
                self.assertEqual(result["state"], "no_games", result)
                self.assertEqual(result["excluded_games"], [dict(game_id="0022600001", reason=reason)])

    def test_postponed_placeholder_without_tip_excluded(self):
        result = self.plan(schedule(game(gameDateTimeUTC=None, gameStatusText="PPD")))
        self.assertEqual(result["state"], "no_games")

    def test_rescheduled_active_game_uses_new_tip(self):
        result = self.plan(schedule(game(tip="2026-11-21T02:00:00Z", postponedStatus="N")))
        self.assertEqual(result["first_tip_at"], "2026-11-20T20:00:00-06:00")

    def test_unknown_time_prevents_exact_plan_even_with_other_games(self):
        for changes in (dict(gameStatusText="TBD"), dict(gameStatusText="TBA"),
                        dict(gameTimeTBD=True), dict(gameDateTimeUTC=None), dict(gameDateTimeUTC="")):
            with self.subTest(changes=changes):
                result = self.error(schedule(game(), game(gid="0022600002", **changes)))
                self.assertEqual(result["unresolved_game_ids"], ["0022600002"])

    def test_tbd_next_nominal_date_blocks_placeholder_misclassification(self):
        # Real NBA TBD games can carry 05:00 UTC (prior Chicago date) placeholders.
        placeholder = game(gid="0022600002", tip="2026-11-21T05:00:00Z", gameStatusText="TBD")
        self.error(schedule(game(), placeholder))
        result = self.plan(schedule(game(), game(gid="0022600002", tip="2026-12-04T05:00:00Z", gameStatusText="TBD")))
        self.assertEqual(result["state"], "ready")

    def test_unknown_teams_or_code_not_silently_dropped(self):
        for changes in (dict(homeTeam=dict(teamId=0, teamTricode="TBD")), dict(gameCode="")):
            self.error(schedule(game(**changes)))

    def test_duplicate_games_and_dates(self):
        self.error(schedule(game(), game()))
        data = schedule(game())
        data["leagueSchedule"]["gameDates"].append(copy.deepcopy(data["leagueSchedule"]["gameDates"][0]))
        self.error(data)

    def test_bad_schema_league_season_and_date(self):
        cases = [{}, [], dict(leagueSchedule=[]), schedule(season="2025-26")]
        for field, value in (("leagueId", "10"), ("gameDates", {}), ("gameDates", [])):
            data = schedule(game()); data["leagueSchedule"][field] = value; cases.append(data)
        for data in cases:
            with self.subTest(data=data): self.error(data)
        for day in ("20261120", "2026-02-30", "2026-1-01", "2025-11-20"):
            self.error(schedule(game()), day)

    def test_bad_game_fields_fail_visibly(self):
        changes = [dict(gameId="0022600000"), dict(gameStatus=2, gameStatusText="Mystery"),
                   dict(gameStatusText="8:00 pm ET"), dict(gameId=226000001), dict(gameId="0022500001"), dict(gameId="0092600001"),
                   dict(gameStatus=4), dict(gameStatus=True), dict(gameStatus="1"),
                   dict(gameStatusText="Mystery"), dict(gameStatusText=None),
                   dict(postponedStatus="?"), dict(postponedStatus=None), dict(gameTimeTBD="true"),
                   dict(gameDateEst="2026-11-19T00:00:00Z"), dict(gameCode="20261119/ATLBOS"),
                   dict(gameCode="20261120/BOSATL"), dict(gameDateTimeUTC="2026-11-21T00:00:00"),
                   dict(gameDateTimeUTC="2026-11-21T00:00:00-06:00"),
                   dict(gameDateTimeUTC="2026-11-22T00:00:00Z"),
                   dict(awayTeam=dict(teamId=1610612738, teamTricode="BOS")),
                   dict(gameStatus=3, gameStatusText="Scheduled"),
                   dict(gameStatus=2, gameStatusText="Final"),
                   dict(gameStatus=3, gameStatusText="PPD")]
        for change in changes:
            with self.subTest(change=change): self.error(schedule(game(**change)))

    def test_live_and_final_keep_original_tip_for_recovery(self):
        for status, text in ((1, "7:00 pm ET"), (2, "Q1 05:15"), (2, "Halftime"), (3, "Final"), (3, "Final/OT2")):
            self.assertEqual(self.plan(schedule(game(gameStatus=status, gameStatusText=text)))["state"], "ready")

    def test_schema_shapes_rejected(self):
        for entry in (None, dict(gameDate="11/20/2026", games=[]),
                      dict(gameDate="11/20/2026 00:00:00", games={}),
                      dict(gameDate="11/20/2026 00:00:00", games=[None])):
            data = schedule(game());data["leagueSchedule"]["gameDates"] = [entry];self.error(data)


class SourceAndRolesTests(unittest.TestCase):
    def test_exact_role_profiles_and_no_deployment(self):
        config = p.strict_json(Path(p.__file__).with_name("daily_roles.json").read_bytes())
        roles = p.validate_profiles(config)
        self.assertEqual(set(roles), {"Admin", "Codex", "Supervisor", "Bridge"})
        self.assertEqual(roles["Supervisor"], dict(model="gpt-6.1-sol", reasoning_effort="high", fork_turns="none"))
        for role in roles:
            for key, value in (("model", "substitute"), ("reasoning_effort", "max"), ("fork_turns", "all")):
                changed = copy.deepcopy(config);changed["roles"][role][key] = value
                with self.assertRaises(ValueError): p.validate_profiles(changed)
        for change in ("missing", "extra", "extra_control", "scheduler", "writer"):
            altered = copy.deepcopy(config)
            if change == "missing": del altered["roles"]["Admin"]
            if change == "extra": altered["roles"]["Other"] = roles["Bridge"]
            if change == "extra_control": altered["roles"]["Codex"]["fallback"] = True
            if change == "scheduler": altered["creates_scheduler"] = True
            if change == "writer": altered["creates_sheet_writer"] = True
            with self.assertRaises(ValueError): p.validate_profiles(altered)

    def test_saved_payload_and_envelope_provenance(self):
        payload = schedule(game())
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/"schedule.json"
            raw = json.dumps(payload).encode();file.write_bytes(raw)
            value, source = p.load_schedule(file)
            self.assertEqual(value, payload)
            self.assertEqual(source["input_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertIsNone(source["fetched_at"])
            envelope = dict(payload=payload, url=p.SCHEDULE_URL, fetched_at="2026-11-19T12:00:00Z")
            file.write_text(json.dumps(envelope))
            value, other = p.load_schedule(file, label="Root-fetched snapshot")
            self.assertEqual(other["mode"], "saved_envelope")
            self.assertEqual(other["payload_sha256"], source["payload_sha256"])
            self.assertEqual(other["label"], "Root-fetched snapshot")
            self.assertEqual(other["fetched_at"], envelope["fetched_at"])
            for key, bad in (("url", "https://example.com"), ("fetched_at", "yesterday")):
                changed = dict(envelope);changed[key] = bad;file.write_text(json.dumps(changed))
                with self.assertRaises(ValueError): p.load_schedule(file)

    def test_duplicate_json_keys_and_nonstandard_numbers_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'\xff', b'{'):
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)): p.strict_json(raw)

    def test_fetch_uses_existing_nba_headers(self):
        with patch.object(p.urllib.request, "urlopen") as opened:
            response = opened.return_value.__enter__.return_value
            response.geturl.return_value = p.SCHEDULE_URL
            response.read.return_value = json.dumps(schedule(game())).encode()
            _, source = p.load_schedule()
            request = opened.call_args.args[0]
            self.assertEqual(request.full_url, p.SCHEDULE_URL)
            self.assertEqual(request.get_header("Referer"), "https://www.nba.com/")
            self.assertEqual(source["mode"], "fetch")
            self.assertIsNotNone(source["fetched_at"])
            self.assertIsNone(source["read_at"])

    def test_cli_error_json_exit_and_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp)/"schedule.json";file.write_text(json.dumps(schedule(game())))
            for day, state, code in (("2026-11-20", "ready", 0), ("bad", "error", 2)):
                stdout = io.StringIO()
                with redirect_stdout(stdout): actual = p.main(["--date", day, "--schedule-json", str(file)])
                self.assertEqual(actual, code);self.assertEqual(json.loads(stdout.getvalue())["state"], state)
            file.unlink()
            with redirect_stdout(io.StringIO()) as output:
                code = p.main(["--date", "2026-11-20", "--schedule-json", str(file)])
            self.assertEqual(code, 2);self.assertEqual(json.loads(output.getvalue())["state"], "error")


if __name__ == "__main__":
    unittest.main()
