import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from review_guard import comparable, has_dimension, load, validate


class ReviewGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = self.save('raw.json', {'payload': {'parameters': {'GeneralRange': 'Catch and Shoot'},
                                                    'resultSets': [{'headers': ['FG3A'], 'rowSet': [[4]]}]}})
        self.evidence = {'T': {'rotations': [
            {'game': 'g1', 'date': '2026-11-17', 'players': [{'id': 1, 'minutes': 20, 'pa': 4}, {'id': 2, 'minutes': 30, 'pa': 2}]},
            {'game': 'g2', 'date': '2026-11-18', 'players': [{'id': 1, 'minutes': 30, 'pa': 8}]},
            {'game': 'g3', 'date': '2026-11-19', 'players': [{'id': 2, 'minutes': 30, 'pa': 2}]},
            {'game': 'future', 'date': '2026-11-20', 'players': [{'id': 1, 'minutes': 99, 'pa': 99}]}
        ]}}
        self.rotation = self.save('rotation.json', self.evidence)
        self.ledger = []
        for stage in range(1, 5):
            for candidate, decision in [('A -> B', 'Advance'), ('B -> A', 'Watchlist')]:
                self.ledger.append(dict(stage=stage, candidate=candidate, cutoff='2026-11-19', decision=decision,
                    execution='completed', figures={'own': 15, 'allowed': 16}, source_refs=[self.raw],
                    reason=f'{candidate} pass{stage} specific assessment', offense_strength='Observed attempts',
                    defensive_concession='Allowed opportunities', strongest_contradiction='Noisy coverage',
                    comparison=dict(offense_baseline=15, defense_concession=16, units='attempts/100', window='season', incremental_effect='Small supporting benefit'),
                    decision_review=dict(previous=decision, current=decision, effect='neutral', rationale='Specific evidence leaves core decision unchanged')))
        comp = dict(source_ref=self.rotation, team='T', present=[2], absent=[],
                    summary=comparable(self.evidence, 'T', 1, '2026-11-19', [2]),
                    sample_caveat='One player appearance; confounded participation.', chosen_adjustment='Use observed role with uncertainty.')
        player = dict(candidate='A -> B', player_id=1, fits=[dict(dimension='defender_distance', status='unverified', boost_claimed=False, limitation='No player distance source; fit unverified.')],
                      rotation_comparables=[comp], conversion_baseline=dict(made=1, attempts=4, window='season', selection_reason='Broader baseline than last game', source_refs=[self.raw]),
                      range_label='judgment_band', range_reason='Observed role, explicit adjustment and uncertain conversion.',
                      minutes_band=[18, 25], attempts_band=[3, 6], conservative_makes_band=[0, 2], stretch_makes_band=[2, 3])
        self.review = dict(slate_date='2026-11-20', cutoff='2026-11-19', weights=dict(core=92.5, creation=5, oreb_max=2.5),
                           expected_candidates=['A -> B', 'B -> A'], final_decisions={'A -> B': 'Advance', 'B -> A': 'Watchlist'}, finalists=['A -> B'],
                           countercases={'A -> B': dict(reject_case='Coverage weakens confidence.', response='Absolute volume retains modest thesis.', source_refs=[self.raw])},
                           watchlist_challenge=dict(candidate='B -> A', promotion_case='Specific concession could help.', response='Weak offense still unresolved.', source_refs=[self.raw]),
                           exploited_dimensions={'A -> B': ['defender_distance']}, players=[player],
                           audit=dict(data='accepted', reasoning='accepted', publication='not_checked', visual='not_checked', source_refs=[self.raw]))

    def save(self, name, data):
        raw = json.dumps(data).encode()
        (self.root / name).write_bytes(raw)
        return dict(path=name, sha256=hashlib.sha256(raw).hexdigest())

    def codes(self):
        return {x['code'] for x in validate(self.ledger, self.review, self.root)}

    def test_complete_honest_unverified_fit_and_unchanged_decision_pass(self):
        self.assertEqual(self.codes(), set())

    def test_copied_supporting_reasons_fail(self):
        for row in self.ledger:
            if row['stage'] == 3: row['reason'] = 'Creation layer inspected; carry status unchanged.'
        self.assertIn('boilerplate', self.codes())

    def test_no_comparison_or_fresh_decision_review_fails(self):
        self.ledger[-1].pop('comparison')
        self.ledger[-1].pop('decision_review')
        self.assertTrue({'comparison', 'decision_review'} <= self.codes())

    def test_catch_shoot_is_not_distance_evidence(self):
        self.assertTrue(has_dimension(load(self.root / 'raw.json'), 'catch_and_shoot'))
        self.assertFalse(has_dimension(load(self.root / 'raw.json'), 'defender_distance'))
        other = self.save('other.json', load(self.root / 'raw.json'))
        self.review['players'][0]['fits'] = [dict(dimension='defender_distance', status='verified', coverage='matched', source_refs=[self.raw, other], game_ids=['g1'], offense_value=2, defense_value=3, units='attempts/100', window='season')]
        self.assertIn('fit_dimension', self.codes())

    def test_real_distance_sources_can_pass(self):
        for name in ['own.json', 'opp.json']:
            self.save(name, {'payload': {'resultSets': [{'headers': ['CLOSE_DEF_DIST_RANGE', 'FG3A'], 'rowSet': [['6+ Feet', 4]]}]}})
        refs = [dict(path=n, sha256=hashlib.sha256((self.root/n).read_bytes()).hexdigest()) for n in ['own.json', 'opp.json']]
        self.review['players'][0]['fits'] = [dict(dimension='defender_distance', status='verified', coverage='matched', source_refs=refs, game_ids=['g1'], offense_value=2, defense_value=3, units='attempts/100', window='season')]
        self.assertEqual(self.codes(), set())

    def test_unverified_fit_cannot_claim_boost(self):
        self.review['players'][0]['fits'][0]['boost_claimed'] = True
        self.assertIn('fit_uncertainty', self.codes())

    def test_rotation_recomputed_and_dnp_not_fabricated(self):
        x = comparable(self.evidence, 'T', 1, '2026-11-19', [2])
        self.assertEqual((x['team_games'], x['player_appearances'], x['unobserved_target_games']), (2, 1, 1))
        self.assertEqual(x['minutes_mean'], 20)
        self.assertNotIn('future', x['game_ids'])

    def test_wrong_rotation_denominator_fails(self):
        self.review['players'][0]['rotation_comparables'][0]['summary']['minutes_mean'] = 10
        self.assertIn('rotation_mismatch', self.codes())

    def test_joint_participation_and_conflicting_ids(self):
        x = comparable(self.evidence, 'T', 1, '2026-11-19', absent=[2])
        self.assertEqual(x['three_pa_mean'], 8)
        with self.assertRaises(ValueError): comparable(self.evidence, 'T', 1, '2026-11-19', [2], [2])
        with self.assertRaises(ValueError): comparable(self.evidence, 'T', 1, '2026-11-19', [999])

    def test_duplicate_game_not_counted_twice(self):
        self.evidence['T']['rotations'].append(copy.deepcopy(self.evidence['T']['rotations'][0]))
        with self.assertRaises(ValueError): comparable(self.evidence, 'T', 1, '2026-11-19')

    def test_missing_or_altered_source_fails(self):
        (self.root/'raw.json').write_text('{}')
        self.assertIn('source_invalid', self.codes())

    def test_missing_pass_wrong_order_cutoff_or_weights_fails(self):
        self.ledger.pop(0)
        self.ledger.reverse()
        self.ledger[0]['cutoff'] = '2026-11-20'
        self.review['weights']['creation'] = 25
        self.assertTrue({'coverage', 'order', 'cutoff', 'weights'} <= self.codes())

    def test_countercase_and_alternative_are_required(self):
        self.review['countercases'] = {}
        self.review['watchlist_challenge'] = {}
        self.assertTrue({'countercase', 'watchlist_challenge'} <= self.codes())

    def test_rejected_core_can_be_explicitly_not_applicable(self):
        self.review['final_decisions']['B -> A'] = 'Reject'
        for row in self.ledger:
            if row['candidate'] == 'B -> A':
                row['decision'] = 'Reject'
                if row['stage'] > 1: row['execution'] = 'not_applicable'
        self.assertEqual(self.codes(), set())

    def test_watchlist_cannot_be_skipped_or_player_rescued(self):
        self.ledger[-1]['execution'] = 'not_applicable'
        self.review['players'][0]['candidate'] = 'B -> A'
        self.assertTrue({'skip', 'player_rescue'} <= self.codes())

    def test_ranges_and_conversion_must_be_explained(self):
        self.review['players'][0]['conversion_baseline']['made'] = 9
        self.review['players'][0]['range_reason'] = ''
        self.review['players'][0]['attempts_band'] = [7, 2]
        self.assertTrue({'conversion', 'range_reasoning', 'range_bounds'} <= self.codes())

    def test_partial_pass_needs_consequence(self):
        self.ledger[0]['execution'] = 'partial'
        self.assertIn('missing', self.codes())

    def test_arithmetic_acceptance_is_not_full_audit(self):
        self.review['audit'].pop('reasoning')
        self.review['audit'].pop('publication')
        self.assertTrue({'audit_incomplete', 'audit_scope'} <= self.codes())

    def test_draft_does_not_require_pretend_audit_acceptance(self):
        self.review.pop('audit')
        self.review.pop('countercases')
        self.review.pop('watchlist_challenge')
        self.assertEqual(validate(self.ledger, self.review, self.root, 'draft'), [])
        self.assertIn('audit_incomplete', self.codes())

    def test_zero_finalists_valid_no_quota(self):
        self.review['finalists'] = []
        self.review['players'] = []
        self.assertEqual(self.codes(), set())

    def test_nonfinite_and_duplicate_json_rejected(self):
        for raw in ['{"a":NaN}', '{"a":1,"a":2}', '{"a":1e999}']:
            (self.root/'bad.json').write_text(raw)
            with self.assertRaises(ValueError): load(self.root/'bad.json')

    def test_malformed_fit_is_an_issue_not_a_crash(self):
        self.review['players'][0]['fits'].append(None)
        self.assertIn('fit_coverage', self.codes())


if __name__ == '__main__':
    unittest.main()
