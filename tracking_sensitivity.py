"""Decompose schedule-adjusted opportunities and check full shot coverage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def grade(rows, defense):
    actual = [row for row in rows if row['defense'] == defense]
    exposure = expected = baseline_expected = assigned_quality = attempts = 0
    eligible = 0
    for row in actual:
        baseline = [other for other in rows if other['offense'] == row['offense'] and other['defense'] != defense]
        if not baseline:
            continue
        base_poss = sum(other['possessions'] for other in baseline)
        base_attempts = sum(sum(other['attempts']) for other in baseline)
        base_expected = sum(other['expected_makes'] for other in baseline)
        if not base_poss or not base_attempts:
            continue
        n_attempts = sum(row['attempts'])
        exposure += row['possessions']
        expected += row['expected_makes']
        baseline_expected += base_expected / base_poss * row['possessions']
        assigned_quality += base_expected / base_attempts * n_attempts
        attempts += n_attempts
        eligible += 1
    if not exposure or not attempts:
        return None
    adjusted = (expected - baseline_expected) / exposure * 100
    quality = (expected - assigned_quality) / exposure * 100
    volume = (assigned_quality - baseline_expected) / exposure * 100
    if abs(adjusted - quality - volume) >= 1e-10:
        raise ValueError('Volume and quality decomposition does not reconcile')
    return {'games': eligible, 'possessions': exposure, 'adjusted_per100': adjusted,
            'volume_contribution_per100': volume, 'quality_contribution_per100': quality,
            'expected_rate_pct': expected / attempts * 100,
            'opponent_expected_rate_pct': assigned_quality / attempts * 100,
            'quality_difference_pp': (expected - assigned_quality) / attempts * 100}


def sensitivity(analysis):
    records = analysis['team_games']
    full = [row for row in records if sum(row['attempts']) == row['box_attempts']
            and sum(row['makes']) == row['box_makes']]
    results = {}
    for defense in sorted({row['defense'] for row in records}):
        results[defense] = {'all_matched': grade(records, defense), 'fully_tracked_only': grade(full, defense)}
    return {'full_team_games': len(full), 'defenses': results,
            'cutoff': analysis['audit']['cutoff'],
            'method': analysis.get('method'), 'input_method': analysis.get('input_method'),
            'source_snapshot': analysis.get('source_snapshot'),
            'analysis_sha256': hashlib.sha256(json.dumps(analysis, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'interpretation': 'Sensitivity to shot completeness; not an unbiased missingness correction. Same pooled bucket weights retained.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('tracking/current'))
    args = parser.parse_args(argv)
    analysis = json.loads((args.data_dir / 'analysis.json').read_text())
    output = sensitivity(analysis)
    (args.data_dir / 'sensitivity.json').write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
