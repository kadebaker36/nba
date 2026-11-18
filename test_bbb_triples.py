"""Focused tests for percentile direction, data integrity and slate construction."""
import copy
import unittest
from datetime import date
import bbb_triples as b


class ScreenerTests(unittest.TestCase):
    def tables(self):
        base, advanced, opponent = {}, {}, {}
        for i in range(30):
            base[i] = dict(TEAM_ID=i, TEAM_NAME=f"Team {i}", GP=10, FG3A=20+i, FG3_PCT=.30+i/1000)
            advanced[i] = dict(TEAM_ID=i, GP=10, OREB_PCT=.20+i/1000, DREB_PCT=.60+i/1000, PACE=90+i/10, POSS=1000)
            opponent[i] = dict(TEAM_ID=i, GP=10, OPP_FG3A=20+i)
        return base, advanced, opponent

    def test_midrank_ties_and_endpoints(self):
        p = b.percentiles({"a": 1, "b": 2, "c": 2, "d": 3})
        self.assertEqual(p, dict(a=0, b=50, c=50, d=100))
        self.assertEqual(set(b.percentiles({i: 5 for i in range(30)}).values()), {50})

    def test_rebound_direction_and_volume(self):
        rows, health = b.join_window(*self.tables(), set(range(30)))
        self.assertTrue(health["league_percentiles_available"])
        self.assertEqual(rows[29]["three_volume_pctile"], 100)
        self.assertEqual(rows[29]["oreb_pctile"], 100)
        self.assertEqual(rows[29]["dreb_weakness_pctile"], 0)
        self.assertEqual(rows[0]["dreb_weakness_pctile"], 100)

    def test_missing_teams_do_not_receive_zero_or_fake_percentile(self):
        tables = self.tables()
        for t in tables:
            del t[29]
        rows, health = b.join_window(*tables, set(range(30)))
        self.assertFalse(health["league_percentiles_available"])
        self.assertNotIn(29, rows)
        self.assertTrue(all(r["three_volume_pctile"] is None for r in rows.values()))

    def test_zero_gp_not_ranked(self):
        tables = self.tables()
        for t in tables:
            t[29]["GP"] = 0
        rows, health = b.join_window(*tables, set(range(30)))
        self.assertNotIn(29, rows)
        self.assertFalse(health["league_percentiles_available"])

    def test_mismatched_coverage_or_games_rejected(self):
        tables = self.tables()
        del tables[0][29]
        with self.assertRaises(ValueError):
            b.join_window(*tables, set(range(30)))
        tables = self.tables()
        tables[1][1]["GP"] = 9
        with self.assertRaises(ValueError):
            b.join_window(*tables, set(range(30)))

    def test_nonfinite_and_bad_units_rejected(self):
        for key, bad in (("DREB_PCT", 75), ("PACE", float("nan"))):
            tables = self.tables()
            tables[1][0][key] = bad
            with self.assertRaises(ValueError):
                b.join_window(*tables, set(range(30)))

    def test_both_directions_use_opponent_defense(self):
        rows, _ = b.join_window(*self.tables(), set(range(30)))
        games = [dict(game_id="0022600001", away_id=0, home_id=29, status="Scheduled")]
        matches = b.matchup_rows(games, {0:"AAA", 29:"BBB"}, "current_season", rows)
        self.assertEqual(len(matches), 2)
        a = next(r for r in matches if r["offense"] == "AAA")
        self.assertEqual(a["perimeter_vulnerability_pctile"], 100)
        self.assertEqual(a["dreb_weakness_pctile"], 0)
        self.assertEqual(a["three_volume_pctile"], 0)
        self.assertEqual(a['own_three_pa_per100'], 20)
        self.assertEqual(a['opponent_three_pa_allowed_per100'], 49)
        self.assertAlmostEqual(a['illustrative_game_possessions'], (90+92.9)/2)
        self.assertAlmostEqual(a['illustrative_three_pa'], 34.5*((90+92.9)/2)/100)

    def test_rebounds_do_not_create_a_hidden_sort_or_qualification_score(self):
        rows, _ = b.join_window(*self.tables(), set(range(30)))
        games = [dict(game_id='0022600001', away_id=0, home_id=29, status='Scheduled')]
        first = b.matchup_rows(games, {0:'AAA', 29:'BBB'}, 'current_season', rows)
        rows[0]['oreb_pctile'], rows[29]['oreb_pctile'] = 100, 0
        rows[0]['dreb_weakness_pctile'], rows[29]['dreb_weakness_pctile'] = 100, 0
        second = b.matchup_rows(games, {0:'AAA', 29:'BBB'}, 'current_season', rows)
        self.assertEqual([r['offense'] for r in first], ['AAA', 'BBB'])
        self.assertEqual([r['offense'] for r in second], ['AAA', 'BBB'])
        self.assertTrue(all('components_at_or_above_75' not in r and 'weakest_component' not in r for r in second))

    def test_date_boundaries(self):
        self.assertEqual(b.season_for(date(2026, 10, 22)), "2026-27")
        self.assertEqual(b.season_for(date(2027, 1, 1)), "2026-27")
        self.assertEqual(b.previous_season("2026-27"), "2025-26")
        url = b.stats_url("2026-27", date(2026, 10, 21), 10, "Base")
        self.assertIn("DateTo=10%2F21%2F2026", url)
        self.assertIn("LastNGames=10", url)
        self.assertIn("PerMode=Per100Possessions", url)

    def test_schedule_rejects_wrong_season_and_duplicates(self):
        teams = [{"teamId":1610612737+i,"teamTricode":f"T{i+1}"} for i in range(30)]
        games = [dict(gameId=f"002260{i:04}", homeTeam=teams[i], awayTeam=teams[i+1], gameStatusText="Scheduled") for i in range(0,30,2)]
        p = {"leagueSchedule": {"seasonYear":"2026-27", "gameDates":[{"gameDate":"10/22/2026 00:00:00", "games":games}]}}
        roster, slate = b.slate_from_schedule(p, date(2026,10,22), "2026-27")
        self.assertEqual((len(roster), len(slate)), (30,15))
        with self.assertRaises(ValueError):
            b.slate_from_schedule(p, date(2026,10,22), "2025-26")
        p["leagueSchedule"]["gameDates"][0]["games"].append(copy.deepcopy(games[0]))
        with self.assertRaises(ValueError):
            b.slate_from_schedule(p, date(2026,10,22), "2026-27")


if __name__ == "__main__":
    unittest.main()
