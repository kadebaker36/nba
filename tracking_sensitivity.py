import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description='Tracking completeness sensitivity and volume/quality decomposition')
parser.add_argument('--data-dir', type=Path, default=Path('tracking/current'))
args = parser.parse_args()
root = args.data_dir
analysis = json.loads((root / 'analysis.json').read_text())
records = analysis['team_games']
weights = analysis['audit']['bucket_make_rates']

def grade(rows, defense):
    actual = [row for row in rows if row['defense'] == defense]
    exposure = expected = baseline_expected = assigned_quality = attempts = makes = 0
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
        makes += sum(row['makes'])
        eligible += 1
    if not exposure or not attempts:
        return None
    adjusted = (expected - baseline_expected) / exposure * 100
    quality = (expected - assigned_quality) / exposure * 100
    volume = (assigned_quality - baseline_expected) / exposure * 100
    assert abs(adjusted - quality - volume) < 1e-10
    return {'games': eligible, 'possessions': exposure, 'adjusted_per100': adjusted,
            'volume_contribution_per100': volume, 'quality_contribution_per100': quality,
            'expected_rate_pct': expected / attempts * 100,
            'opponent_expected_rate_pct': assigned_quality / attempts * 100,
            'quality_difference_pp': (expected - assigned_quality) / attempts * 100}

full = [row for row in records if sum(row['attempts']) == row['box_attempts'] and sum(row['makes']) == row['box_makes']]
results = {}
for defense in sorted({row['defense'] for row in records}):
    results[defense] = {'all_matched': grade(records, defense), 'fully_tracked_only': grade(full, defense)}
(root / 'sensitivity.json').write_text(json.dumps({'full_team_games': len(full), 'defenses': results}, indent=2))
print(json.dumps({'full_team_games': len(full), 'defenses': results}, indent=2))
