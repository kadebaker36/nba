import copy
import unittest
import tempfile
from pathlib import Path
from datetime import date
from bbb_connections import parse_game, build_connections

HOME, AWAY = 1610612738, 1610612765


def event(n, kind, team=HOME, pid=10, clock="PT05M00.00S", **kwargs):
    return dict(actionNumber=n, orderNumber=n*100, period=1, clock=clock,
                teamId=team, personId=pid, actionType=kind, subType="",
                qualifiers=[], isFieldGoal=0, **kwargs)


def shot(n, kind="3pt", made=False, second=False, team=HOME, **kwargs):
    e=event(n,kind,team=team,**kwargs)
    e.update(isFieldGoal=1, shotResult="Made" if made else "Missed",
             qualifiers=["2ndchance"] if second else [])
    return e


def board(n, source, team=HOME, pid=20, **kwargs):
    e=event(n,"rebound",team=team,pid=pid,**kwargs)
    e.update(subType="offensive",shotActionNumber=source)
    return e


def box(home=(2,0,2,0,1,0,1,0),away=(0,0,0,0,0,0,0,0)):
    keys=("fieldGoalsAttempted","fieldGoalsMade","threePointersAttempted","threePointersMade",
          "reboundsOffensive","assists","secondChancePointsAttempted","secondChancePointsMade")
    return {"game":{"gameId":"0022600001","gameStatus":3,
        "homeTeam":{"teamId":HOME,"teamTricode":"BOS","statistics":dict(zip(keys,home))},
        "awayTeam":{"teamId":AWAY,"teamTricode":"DET","statistics":dict(zip(keys,away))}}}


def parse(actions, score=None):
    return parse_game({"game":{"gameId":"0022600001","actions":actions}},score or box(),"0022600001")


class ConnectionTests(unittest.TestCase):
    def test_missed_three_counts_and_passer_is_unknown(self):
        p=parse([shot(1),board(2,1),shot(3,second=True,clock="PT04M55.00S")])
        self.assertEqual(p["totals"][HOME]["oreb_next3"],1)
        self.assertEqual(p["totals"][HOME]["assisted_three_pm"],0)
        self.assertEqual(p["audit"][0]["elapsed_seconds"],5)
        self.assertEqual(p["threes"][-1]["passer_on_miss"],"unavailable")

    def test_recorded_assist_separate_from_rebounder(self):
        a=shot(3,made=True,second=True,assistPersonId=30,assistPlayerNameInitial="Passer")
        p=parse([shot(1),board(2,1),a],box(home=(2,1,2,1,1,1,1,1)))
        self.assertEqual(p["audit"][0]["rebounder_id"],20)
        self.assertEqual(p["audit"][0]["assister_id"],30)
        self.assertEqual(p["totals"][HOME]["assisted_three_pm"],1)

    def test_repeated_rebounds_each_have_one_next_shot(self):
        p=parse([shot(1),board(2,1),shot(3,second=True),board(4,3),shot(5,second=True)],
                box(home=(3,0,3,0,2,0,2,0)))
        self.assertEqual(len(p["audit"]),2)
        self.assertEqual(p["totals"][HOME]["oreb_next3"],2)
        self.assertEqual([t["linked_rebound_action"] for t in p["threes"]],[None,2,4])

    def test_putback_does_not_become_next_three(self):
        p=parse([shot(1),board(2,1),shot(3,kind="2pt",second=True),board(4,3,pid=None),shot(5,second=True)],
                box(home=(3,0,2,0,1,0,2,0)))
        self.assertEqual(p["audit"][0]["outcome"],"next_2pa")
        self.assertEqual(p["totals"][HOME]["oreb_next3"],0)
        self.assertEqual(p["totals"][HOME]["source_second_three_pa"],1)

    def test_turnover_free_throw_and_period_end_stop_links(self):
        for kind in ("turnover","freethrow","period"):
            a=event(3,kind)
            p=parse([shot(1),board(2,1),a,shot(4)],box(home=(2,0,2,0,1,0,0,0)))
            self.assertEqual(p["totals"][HOME]["oreb_next3"],0)

    def test_opponent_shot_stops_link(self):
        p=parse([shot(1),board(2,1),shot(3,team=AWAY),shot(4)],
                box(home=(2,0,2,0,1,0,0,0),away=(1,0,1,0,0,0,0,0)))
        self.assertEqual(p["audit"][0]["outcome"],"opponent_field_goal_attempt")

    def test_nontechnical_foul_does_not_imply_possession_change(self):
        a=event(3,"foul",team=AWAY);a["subType"]="personal"
        p=parse([shot(1),board(2,1),a,shot(4,second=True)])
        self.assertEqual(p["totals"][HOME]["oreb_next3"],1)

    def test_technical_free_throw_can_preserve_link(self):
        a=event(3,"freethrow",team=AWAY);a["description"]="Technical Free Throw"
        p=parse([shot(1),board(2,1),a,shot(4,second=True)])
        self.assertEqual(p["totals"][HOME]["oreb_next3"],1)

    def test_corrected_order_not_action_number_or_array_order(self):
        a=[shot(1),board(10,1),shot(3,second=True)]
        a[1]["orderNumber"]=200
        p=parse([a[2],a[0],a[1]])
        self.assertEqual(p["threes"][-1]["linked_rebound_action"],10)

    def test_missing_tag_keeps_reconstructed_three_and_flags_disagreement(self):
        p=parse([shot(1),board(2,1),shot(3)],box(home=(2,0,2,0,1,0,0,0)))
        self.assertEqual(p["totals"][HOME]["untagged_next_fga"],1)
        self.assertEqual(p["totals"][HOME]["untagged_next3"],1)
        self.assertEqual(p["totals"][HOME]["oreb_next3"],1)
        self.assertEqual(p["totals"][HOME]["source_second_three_pa"],0)
        self.assertEqual(p["audit"][0]["outcome"],"next_3pa")
        self.assertFalse(p["audit"][0]["source_second_chance"])
        self.assertEqual(p["threes"][-1]["linked_rebound_action"],2)

    def test_missing_tag_on_two_pointer_is_not_a_three(self):
        p=parse([shot(1),board(2,1),shot(3,kind="2pt")],box(home=(2,0,1,0,1,0,0,0)))
        self.assertEqual(p["totals"][HOME]["untagged_next_fga"],1)
        self.assertEqual(p["totals"][HOME]["untagged_next3"],0)
        self.assertEqual(p["totals"][HOME]["oreb_next3"],0)
        self.assertEqual(p["audit"][0]["outcome"],"next_2pa")

    def test_bad_identity_duplicate_missing_reference_and_box_mismatch(self):
        actions=[shot(1),board(2,1),shot(3,second=True)]
        score=box();score["game"]["gameId"]="other"
        with self.assertRaises(ValueError):parse(actions,score)
        with self.assertRaises(ValueError):parse(actions+[copy.deepcopy(actions[0])])
        bad=copy.deepcopy(actions);bad[1]["shotActionNumber"]=99
        with self.assertRaises(ValueError):parse(bad)
        score=box();score["game"]["homeTeam"]["statistics"]["threePointersAttempted"]=3
        with self.assertRaises(ValueError):parse(actions,score)

    def test_window_denominators_and_no_partial_league_percentiles(self):
        # Two games, with only the last game producing an assisted OREB three.
        schedule={"leagueSchedule":{"gameDates":[]}}
        feeds={}
        for i,day in ((1,"10/20/2026"),(2,"10/21/2026")):
            gid=f"002260000{i}"
            schedule["leagueSchedule"]["gameDates"].append({"gameDate":day,"games":[
                {"gameId":gid,"gameStatus":3,"homeTeam":{"teamId":HOME},"awayTeam":{"teamId":AWAY}}]})
            a=[shot(1),board(2,1),shot(3,kind="2pt",second=False)] if i==1 else [shot(1),board(2,1),shot(3,made=True,second=True,assistPersonId=30)]
            s=box(home=(2,0,1,0,1,0,0,0)) if i==1 else box(home=(2,1,2,1,1,1,1,1))
            s["game"]["gameId"]=gid
            feeds[gid]=({"game":{"gameId":gid,"actions":a}},s)
        def fetch(url,*args,**kwargs):
            gid=url.rsplit("_",1)[1].removesuffix(".json")
            return feeds[gid][0 if "/playbyplay/" in url else 1], {"url":url}
        windows={w:{"rows":{t:{"gp":gp,"possessions":100*gp} for t in (HOME,AWAY)}}
                 for w,gp in (("current_season",2),("recent",1))}
        with tempfile.TemporaryDirectory() as temp:
            r=build_connections(schedule,date(2026,10,21),1,windows,{HOME:"BOS",AWAY:"DET"},Path(temp),fetch,False,lambda v:{k:99 for k in v})
        self.assertEqual(r["validated_games"],2)
        current=r["windows"]["current_season"][HOME]
        recent=r["windows"]["recent"][HOME]
        self.assertEqual(current["oreb_next3_rate"],.5)
        self.assertTrue(current["association_complete"])
        self.assertEqual(current["next_fga_without_tag"],1)
        self.assertEqual(r["windows"]["current_season"][AWAY]["opp_oreb_next3_rate"],.5)
        self.assertEqual(recent["oreb_next3_rate"],1)
        self.assertEqual(current["assisted_3pm_per100"],.5)
        self.assertEqual(recent["assisted_3pm_per100"],1)
        self.assertIsNone(current["assisted_3pm_per100_pctile"])
        self.assertEqual(r["windows"]["current_season"][AWAY]["opp_assisted_3pm_per100"],.5)
        self.assertIsNone(r["windows"]["current_season"][AWAY]["oreb_next3_rate"])


if __name__ == "__main__":
    unittest.main()
