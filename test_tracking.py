"""Regression checks for source integrity, baseline exclusion and honest coverage."""
import copy
import unittest
from urllib.parse import urlencode

from analyze_tracking import analyze, BUCKETS
from tracking_sensitivity import sensitivity


def fixture():
    games, responses, boxes = [], [], []
    for i, (home, away) in enumerate([(1, 2), (1, 2), (2, 3), (3, 1)], 1):
        day = f'2026-11-0{i}'
        stamp = f'11/0{i}/2026'
        gid = f'002260000{i}'
        games.append(dict(id=gid, date=day, home_id=home, away_id=away, home=f'T{home}', away=f'T{away}'))
        for tid in [home, away]:
            boxes.append([gid, tid, 10, 4])
        for kind in ['advanced', '0', '1', '2', '3']:
            params = dict(DateFrom=stamp, DateTo=stamp, SeasonType='Regular Season', Season='2026-27')
            if kind == 'advanced':
                params.update(MeasureType='Advanced', PerMode='Per100Possessions')
                headers, rows = ['TEAM_ID', 'GP', 'POSS'], [[home, 1, 100], [away, 1, 100]]
            else:
                bucket = int(kind)
                params.update(CloseDefDistRange=BUCKETS[bucket], PerMode='Totals', GeneralRange='Overall')
                headers = ['TEAM_ID', 'GP', 'FG3A', 'FG3M']
                rows = [[tid, 1, [1, 2, 3, 4][bucket], [0, 1, 1, 2][bucket]] for tid in [home, away]]
            responses.append(dict(date=day, kind=kind, source={'url':'https://stats.nba.com/stats/example?'+urlencode(params)},
                                  payload={'parameters':params, 'resultSets':[{'headers':headers, 'rowSet':rows}]}))
    inputs = dict(cutoff='2026-11-04', slate_date='2026-11-05', season='2026-27', games=games, responses=responses,
                  method={'method_commit':'historical-input', 'method_sha256':'historical-hash'})
    box = {'payload':{'resultSets':[{'headers':['GAME_ID', 'TEAM_ID', 'FG3A', 'FG3M'], 'rowSet':boxes}]}}
    return inputs, box


class TrackingTests(unittest.TestCase):
    def test_all_meetings_with_rated_defense_are_excluded_from_baseline(self):
        inputs, box = fixture()
        result = analyze(inputs, box)
        baseline = next(r for r in result['comparisons'] if r['defense']=='T1' and r['offense']=='T2')
        self.assertEqual(baseline['baseline']['games'], 1)
        self.assertEqual(result['audit']['matched_games'], 4)
        self.assertEqual(result['audit']['matched_team_games'], 8)
        for row in result['defenses']:
            self.assertAlmostEqual(row['adjusted_difference_per100'], row['volume_contribution_per100']+row['quality_contribution_per100'])

    def test_excess_attempts_or_makes_never_enter_pooled_estimates(self):
        for field, value in [(2, 101), (3, 1)]:
            inputs, box = fixture()
            inputs['responses'][1]['payload']['resultSets'][0]['rowSet'][0][field] = value
            with self.assertRaisesRegex(ValueError, 'exceed'):
                analyze(inputs, box)

    def test_one_sided_gap_cannot_be_called_a_fully_matched_game(self):
        inputs, box = fixture()
        inputs['responses'][1]['payload']['resultSets'][0]['rowSet'].pop(0)
        result = analyze(inputs, box)
        self.assertEqual(result['audit']['matched_games'], 3)
        self.assertEqual(result['audit']['any_side_matched_games'], 4)
        self.assertEqual(result['audit']['matched_team_games'], 7)
        self.assertEqual(len(result['audit']['missing_team_games']), 1)

    def test_mislabeled_date_bucket_duplicate_and_nonfinite_possessions_rejected(self):
        for kind in ['date', 'bucket', 'duplicate', 'possessions']:
            inputs, box = fixture()
            if kind == 'date': inputs['responses'][0]['payload']['parameters']['DateTo'] = '11/02/2026'
            if kind == 'bucket': inputs['responses'][1]['kind'] = '2'
            if kind == 'duplicate': inputs['responses'].append(copy.deepcopy(inputs['responses'][0]))
            if kind == 'possessions': inputs['responses'][0]['payload']['resultSets'][0]['rowSet'][0][2] = float('nan')
            with self.assertRaises(ValueError): analyze(inputs, box)

    def test_provenance_survives_analysis_and_sensitivity(self):
        inputs, box = fixture()
        result = analyze(inputs, box)
        derived = sensitivity(result)
        self.assertEqual(result['input_method'], inputs['method'])
        self.assertEqual(derived['source_snapshot'], result['source_snapshot'])
        self.assertEqual(derived['method'], result['method'])
        self.assertEqual(derived['cutoff'], inputs['cutoff'])
        self.assertEqual(len(derived['analysis_sha256']), 64)

    def test_zero_capture_is_missing_and_comparison_samples_stay_aligned(self):
        inputs, box = fixture()
        for response in inputs['responses']:
            if response['date']=='2026-11-03' and response['kind']!='advanced':
                for row in response['payload']['resultSets'][0]['rowSet']:
                    if row[0]==3: row[2], row[3] = 0, 0
        result = analyze(inputs, box)
        self.assertEqual(len(result['audit']['missing_team_games']), 1)
        self.assertEqual(result['audit']['matched_team_games'], 7)
        self.assertFalse(any(r['defense']=='T1' and r['offense']=='T2' for r in result['comparisons']))
        for row in result['defenses']:
            if row['adjusted_difference_per100'] is not None:
                self.assertAlmostEqual(row['adjusted_difference_per100'], row['volume_contribution_per100']+row['quality_contribution_per100'])


if __name__ == '__main__':
    unittest.main()
