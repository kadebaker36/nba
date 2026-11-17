import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

parser = argparse.ArgumentParser(description='Schedule-adjusted expected threes from matched NBA tracking')
parser.add_argument('--data-dir', type=Path, default=Path('tracking/current'))
args = parser.parse_args()
ROOT = args.data_dir
inputs = json.loads((ROOT / 'inputs.json').read_text())
box_payload = json.loads((ROOT / 'boxlogs.json').read_text())['payload']

def table(payload):
    result = payload['resultSets'][0]
    return [dict(zip(result['headers'], values)) for values in result['rowSet']]

daily = {}
for response in inputs['responses']:
    if 'error' in response:
        raise ValueError(response)
    rows = table(response['payload'])
    by_team = {int(row['TEAM_ID']): row for row in rows}
    if len(by_team) != len(rows):
        raise ValueError('Duplicate daily team row')
    daily[response['date'], response['kind']] = by_team

boxes = {(str(row['GAME_ID']), int(row['TEAM_ID'])): row for row in table(box_payload)}
if len(boxes) != 2 * len(inputs['games']):
    raise ValueError('Box team-game count does not match the completed schedule')
records = []
missing = []
for game in inputs['games']:
    for side, opponent_side in [('home', 'away'), ('away', 'home')]:
        defense_id, offense_id = game[side + '_id'], game[opponent_side + '_id']
        advanced = daily[game['date'], 'advanced'].get(defense_id)
        buckets = [daily[game['date'], str(index)].get(defense_id) for index in range(4)]
        if not advanced or advanced['GP'] != 1 or any(row is None or row['GP'] != 1 for row in buckets):
            missing.append({'game': game['id'], 'date': game['date'], 'defense': game[side]})
            continue
        possessions = float(advanced['POSS'])
        if possessions <= 0:
            raise ValueError('Invalid possession count')
        attempts = [int(row['FG3A']) for row in buckets]
        makes = [int(row['FG3M']) for row in buckets]
        assert all(0 <= made <= attempted for made, attempted in zip(makes, attempts))
        opponent_box = boxes[game['id'], offense_id]
        records.append({
            'game': game['id'], 'date': game['date'],
            'defense_id': defense_id, 'offense_id': offense_id,
            'defense': game[side], 'offense': game[opponent_side],
            'possessions': possessions, 'attempts': attempts, 'makes': makes,
            'box_attempts': int(opponent_box['FG3A']),
            'box_makes': int(opponent_box['FG3M']),
        })

bucket_attempts = [sum(row['attempts'][index] for row in records) for index in range(4)]
bucket_makes = [sum(row['makes'][index] for row in records) for index in range(4)]
if not records or not all(bucket_attempts):
    raise ValueError('Insufficient matched tracking to estimate all four bucket make rates')
weights = [made / attempted for made, attempted in zip(bucket_makes, bucket_attempts)]
for row in records:
    row['expected_makes'] = sum(a * weight for a, weight in zip(row['attempts'], weights))

def summarize(rows):
    possessions = sum(row['possessions'] for row in rows)
    attempts = sum(sum(row['attempts']) for row in rows)
    makes = sum(sum(row['makes']) for row in rows)
    expected = sum(row['expected_makes'] for row in rows)
    return {
        'games': len(rows), 'possessions': possessions,
        'attempts': attempts, 'makes': makes, 'expected_makes': expected,
        'expected_per100': expected / possessions * 100,
        'actual_per100': makes / possessions * 100,
        'expected_pct': expected / attempts if attempts else None,
        'actual_pct': makes / attempts if attempts else None,
        'actual_minus_expected_pp': (makes - expected) / attempts * 100 if attempts else None,
        'open_per100': sum(row['attempts'][2] for row in rows) / possessions * 100,
        'wide_per100': sum(row['attempts'][3] for row in rows) / possessions * 100,
        'partial_games': sum(sum(row['attempts']) < row['box_attempts'] or sum(row['makes']) < row['box_makes'] for row in rows),
        'excess_games': sum(sum(row['attempts']) > row['box_attempts'] or sum(row['makes']) > row['box_makes'] for row in rows),
    }

by_defense = defaultdict(list)
by_offense = defaultdict(list)
for row in records:
    by_defense[row['defense']].append(row)
    by_offense[row['offense']].append(row)

results = []
comparisons = []
for defense, defense_rows in sorted(by_defense.items()):
    matched_rows = []
    baseline_expected = 0
    opponent_baselines = {}
    for row in defense_rows:
        offense = row['offense']
        if offense not in opponent_baselines:
            other_rows = [other for other in by_offense[offense] if other['defense'] != defense]
            if not other_rows:
                opponent_baselines[offense] = None
                continue
            assert all(other['defense'] != defense for other in other_rows)
            baseline = summarize(other_rows)
            opponent_baselines[offense] = baseline
            comparisons.append({'defense': defense, 'offense': offense, 'baseline': baseline})
        baseline = opponent_baselines[offense]
        if baseline is None:
            continue
        matched_rows.append(row)
        baseline_expected += baseline['expected_per100'] * row['possessions'] / 100
    if not matched_rows:
        results.append({'defense': defense, 'games': 0, 'possessions': 0, 'adjusted_difference_per100': None, 'coverage': 'No matched comparison baseline'})
        continue
    summary = summarize(matched_rows)
    summary['defense'] = defense
    summary['opponent_baseline_per100'] = baseline_expected / summary['possessions'] * 100
    summary['adjusted_difference_per100'] = summary['expected_per100'] - summary['opponent_baseline_per100']
    summary['unique_opponents'] = len(opponent_baselines)
    results.append(summary)

audit = summarize(records)
audit.update({'scheduled_games': len(inputs['games']), 'matched_games': len({row['game'] for row in records}),
              'missing_team_games': missing, 'bucket_attempts': bucket_attempts,
              'bucket_makes': bucket_makes, 'bucket_make_rates': weights,
              'cutoff': inputs.get('cutoff', max(game['date'] for game in inputs['games'])), 'adjustment': 'unshrunk leave-one-defense-out, weighted by matched possessions'})
output = {'audit': audit, 'defenses': results, 'comparisons': comparisons, 'team_games': records}
(ROOT / 'analysis.json').write_text(json.dumps(output, indent=2))
print(json.dumps({'audit': audit}, indent=2))
if results:
    fields = sorted(set().union(*(row.keys() for row in results)))
    with (ROOT / 'defense_summary.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
print(json.dumps({'defenses_with_comparisons': sum(row['games'] > 0 for row in results)}))
