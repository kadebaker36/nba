"""Validate matched tracking and estimate opponent-adjusted three-point opportunities."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from method_policy import metadata
from tracking_sensitivity import grade

BUCKETS = ['0-2 Feet - Very Tight', '2-4 Feet - Tight', '4-6 Feet - Open', '6+ Feet - Wide Open']


def table(payload):
    result = payload['resultSets'][0]
    return [dict(zip(result['headers'], row, strict=True)) for row in result['rowSet']]


def number(value, count=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid numeric tracking or box value')
    if count and int(value) != value:
        raise ValueError('Count must be an integer')
    return int(value) if count else float(value)


def validate_response(response, season):
    if 'error' in response:
        raise ValueError('Failed tracking request: ' + str(response['error']))
    stamp = date.fromisoformat(response['date']).strftime('%m/%d/%Y')
    kind = response['kind']
    params = response['payload']['parameters']
    query = parse_qs(urlparse(response['source']['url']).query, keep_blank_values=True)
    for key, expected in [('DateFrom', stamp), ('DateTo', stamp), ('SeasonType', 'Regular Season')]:
        if params.get(key) != expected or query.get(key) != [expected]:
            raise ValueError('Tracking response date/type differs from its request or assigned day')
    if query.get('Season', query.get('SeasonYear')) != [season]:
        raise ValueError('Tracking source season differs from analysis season')
    # The tracking endpoint echoes a blank SeasonYear; verify the requested season and nonblank echoes.
    for key in ('Season', 'SeasonYear'):
        if params.get(key) and params[key] != season:
            raise ValueError('Tracking response season mismatch')
    if kind == 'advanced':
        expected = {'MeasureType': 'Advanced', 'PerMode': 'Per100Possessions'}
    elif kind in {'0', '1', '2', '3'}:
        expected = {'CloseDefDistRange': BUCKETS[int(kind)], 'PerMode': 'Totals', 'GeneralRange': 'Overall'}
    else:
        raise ValueError('Unexpected tracking response kind')
    for key, value in expected.items():
        if params.get(key) != value or query.get(key) != [value]:
            raise ValueError('Tracking response measure or distance bucket mismatch')


def summarize(rows):
    possessions = sum(row['possessions'] for row in rows)
    attempts = sum(sum(row['attempts']) for row in rows)
    makes = sum(sum(row['makes']) for row in rows)
    expected = sum(row['expected_makes'] for row in rows)
    return {'games': len(rows), 'possessions': possessions, 'attempts': attempts, 'makes': makes,
            'expected_makes': expected,
            'expected_per100': expected / possessions * 100 if possessions else None,
            'actual_per100': makes / possessions * 100 if possessions else None,
            'expected_pct': expected / attempts if attempts else None,
            'actual_pct': makes / attempts if attempts else None,
            'actual_minus_expected_pp': (makes-expected) / attempts * 100 if attempts else None,
            'open_per100': sum(r['attempts'][2] for r in rows) / possessions * 100 if possessions else None,
            'wide_per100': sum(r['attempts'][3] for r in rows) / possessions * 100 if possessions else None,
            'partial_games': sum(sum(r['attempts']) < r['box_attempts'] or sum(r['makes']) < r['box_makes'] for r in rows),
            'excess_games': 0}  # Impossible excess totals are rejected before any estimation.


def analyze(inputs, box_document):
    games = inputs['games']
    if not games:
        raise ValueError('No completed games supplied')
    cutoff = inputs.get('cutoff', max(g['date'] for g in games))
    season = inputs.get('season') or str(date.fromisoformat(cutoff).year - (date.fromisoformat(cutoff).month < 7))
    if '-' not in season:
        season = f'{season}-{str(int(season)+1)[-2:]}'
    if inputs.get('slate_date') and cutoff >= inputs['slate_date']:
        raise ValueError('Tracking cutoff must precede the slate date')
    expected_keys = set()
    game_ids = set()
    for game in games:
        if game['id'] in game_ids or game['date'] > cutoff or game['home_id'] == game['away_id']:
            raise ValueError('Duplicate, future, or invalid scheduled game')
        game_ids.add(game['id'])
        expected_keys.update((game['id'], game[side+'_id']) for side in ['home', 'away'])
    daily = {}
    for response in inputs['responses']:
        validate_response(response, season)
        key = response['date'], response['kind']
        if key in daily:
            raise ValueError('Duplicate daily tracking response')
        rows = table(response['payload'])
        indexed = {int(row['TEAM_ID']): row for row in rows}
        if len(indexed) != len(rows):
            raise ValueError('Duplicate daily team row')
        daily[key] = indexed
    box_rows = table(box_document['payload'])
    boxes = {(str(row['GAME_ID']), int(row['TEAM_ID'])): row for row in box_rows}
    if len(boxes) != len(box_rows) or set(boxes) != expected_keys:
        raise ValueError('Box team-game identities do not match the completed schedule')
    for row in box_rows:
        if number(row['FG3M'], True) > number(row['FG3A'], True):
            raise ValueError('Box makes exceed attempts')
    records, missing = [], []
    for game in games:
        for side, other in [('home', 'away'), ('away', 'home')]:
            defense_id, offense_id = game[side+'_id'], game[other+'_id']
            advanced = daily.get((game['date'], 'advanced'), {}).get(defense_id)
            buckets = [daily.get((game['date'], str(i)), {}).get(defense_id) for i in range(4)]
            if not advanced or advanced['GP'] != 1 or any(r is None or r['GP'] != 1 for r in buckets):
                missing.append({'game': game['id'], 'date': game['date'], 'defense': game[side]})
                continue
            possessions = number(advanced['POSS'])
            if not possessions:
                raise ValueError('Invalid possession count')
            attempts = [number(r['FG3A'], True) for r in buckets]
            makes = [number(r['FG3M'], True) for r in buckets]
            if any(m > a for m, a in zip(makes, attempts)):
                raise ValueError('Tracked bucket makes exceed attempts')
            box = boxes[game['id'], offense_id]
            if sum(attempts) > box['FG3A'] or sum(makes) > box['FG3M']:
                raise ValueError('Tracked totals exceed opposing box score: ' + game['id'] + ' ' + game[side])
            if not sum(attempts) and box['FG3A'] > 0:
                missing.append({'game': game['id'], 'date': game['date'], 'defense': game[side],
                                'reason': 'No captured threes despite nonzero opposing box attempts'})
                continue
            records.append({'game': game['id'], 'date': game['date'], 'defense_id': defense_id,
                'offense_id': offense_id, 'defense': game[side], 'offense': game[other],
                'possessions': possessions, 'attempts': attempts, 'makes': makes,
                'box_attempts': int(box['FG3A']), 'box_makes': int(box['FG3M'])})
    bucket_attempts = [sum(r['attempts'][i] for r in records) for i in range(4)]
    bucket_makes = [sum(r['makes'][i] for r in records) for i in range(4)]
    if not records or not all(bucket_attempts):
        raise ValueError('Insufficient matched tracking to estimate all four bucket make rates')
    weights = [m/a for m, a in zip(bucket_makes, bucket_attempts)]
    for row in records:
        row['expected_makes'] = sum(a*w for a, w in zip(row['attempts'], weights))
    by_defense, by_offense = defaultdict(list), defaultdict(list)
    for row in records:
        by_defense[row['defense']].append(row)
        by_offense[row['offense']].append(row)
    results, comparisons = [], []
    for defense, defense_rows in sorted(by_defense.items()):
        matched, baseline_expected, baselines = [], 0, {}
        for row in defense_rows:
            offense = row['offense']
            if offense not in baselines:
                others = [r for r in by_offense[offense] if r['defense'] != defense]
                eligible_baseline = others and sum(sum(r['attempts']) for r in others) > 0
                baselines[offense] = summarize(others) if eligible_baseline else None
                if eligible_baseline:
                    comparisons.append({'defense': defense, 'offense': offense, 'baseline': baselines[offense]})
            baseline = baselines[offense]
            if baseline is None:
                continue
            matched.append(row)
            baseline_expected += baseline['expected_per100'] * row['possessions'] / 100
        summary = summarize(matched)
        summary.update(defense=defense,
            opponent_baseline_per100=baseline_expected / summary['possessions'] * 100 if matched else None,
            unique_opponents=len(baselines), eligible_unique_opponents=sum(v is not None for v in baselines.values()),
            coverage='Partial tracking estimate; inspect eligible games and possessions')
        summary['adjusted_difference_per100'] = (summary['expected_per100'] - summary['opponent_baseline_per100']) if matched else None
        decomposition = grade(records, defense)
        for key in ['volume_contribution_per100', 'quality_contribution_per100', 'quality_difference_pp']:
            summary[key] = decomposition[key] if decomposition else None
        results.append(summary)
    pairs = Counter(row['game'] for row in records)
    audit = summarize(records)
    audit.update(scheduled_games=len(games), matched_games=sum(n == 2 for n in pairs.values()),
        any_side_matched_games=len(pairs), matched_team_games=len(records), expected_team_games=2*len(games),
        missing_team_games=missing, bucket_attempts=bucket_attempts, bucket_makes=bucket_makes,
        bucket_make_rates=weights, cutoff=cutoff,
        adjustment='unshrunk leave-one-defense-out, weighted by matched possessions')
    digest = lambda x: hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'audit': audit, 'defenses': results, 'comparisons': comparisons, 'team_games': records,
        'method': metadata(), 'input_method': inputs.get('method'),
        'source_snapshot': {'cutoff': cutoff, 'season': season, 'slate_date': inputs.get('slate_date'),
            'inputs_sha256': digest(inputs), 'boxlogs_sha256': digest(box_document),
            'sources': [inputs.get('schedule_source'), box_document.get('source')]
                       + [r.get('source') for r in inputs['responses']]}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('tracking/current'))
    args = parser.parse_args(argv)
    root = args.data_dir
    output = analyze(json.loads((root/'inputs.json').read_text()), json.loads((root/'boxlogs.json').read_text()))
    (root/'analysis.json').write_text(json.dumps(output, indent=2))
    fields = sorted(set().union(*(r.keys() for r in output['defenses'])))
    with (root/'defense_summary.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output['defenses'])
    print(json.dumps({'audit': output['audit'], 'defenses_with_comparisons': sum(r['games'] > 0 for r in output['defenses'])}, indent=2))


if __name__ == '__main__':
    main()
