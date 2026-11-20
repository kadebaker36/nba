#!/usr/bin/env python3
"""Read-only evidence checks. A structural pass is not an analytical audit."""
import argparse
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path
from statistics import mean


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"Nonfinite JSON number: {value}")
    def finite_float(value):
        result = float(value)
        if not math.isfinite(result): invalid(value)
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite_float)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def comparable(evidence, team, player_id, cutoff, present=(), absent=()):
    """Observed participation groups, not medical availability or causal effects.

    Missing target appearances are counted separately, never silently zero-filled.
    """
    date.fromisoformat(cutoff)
    if type(player_id) is not int or any(type(x) is not int for x in (*present, *absent)):
        raise ValueError('Player/condition IDs must be integers')
    games = evidence[team]['rotations']
    known = {p['id'] for g in games for p in g['players']}
    if player_id not in known or not set(present).union(absent) <= known:
        raise ValueError('Unknown player/condition ID in this evidence')
    if set(present) & set(absent) or player_id in set(present).union(absent):
        raise ValueError('Conflicting or self-conditioned participation groups')
    selected, appearances, seen = [], [], set()
    for game in games:
        if game['game'] in seen:
            raise ValueError('Duplicate game in rotation evidence')
        seen.add(game['game'])
        date.fromisoformat(game['date'])
        if game['date'] > cutoff:
            continue
        players = {p['id']: p for p in game['players']}
        if len(players) != len(game['players']):
            raise ValueError('Duplicate player in rotation evidence')
        if not set(present) <= players.keys() or set(absent) & players.keys():
            continue
        selected.append(game['game'])
        if player_id in players:
            p = players[player_id]
            if not number(p['minutes']) or p['minutes'] <= 0 or not number(p['pa']) or p['pa'] < 0:
                raise ValueError('Invalid rotation numerator/minutes')
            appearances.append((game['game'], p))
    return dict(condition_type='observed_participation', game_ids=selected,
                appearance_game_ids=[g for g, _ in appearances],
                team_games=len(selected), player_appearances=len(appearances),
                unobserved_target_games=len(selected)-len(appearances),
                minutes_mean=mean(p['minutes'] for _, p in appearances) if appearances else None,
                three_pa_mean=mean(p['pa'] for _, p in appearances) if appearances else None,
                caveat='Descriptive, confounded participation groups. Not an injury effect; '
                       'unobserved target games are not proven DNPs or zero attempts.')


def has_dimension(data, dimension):
    payload = data.get('payload', data)
    params = payload.get('parameters', {})
    sets = payload.get('resultSets', [])
    headers = {h for s in sets if isinstance(s, dict) for h in s.get('headers', [])}
    if dimension == 'defender_distance':
        return bool(params.get('CloseDefDistRange')) or 'CLOSE_DEF_DIST_RANGE' in headers
    if dimension == 'location':
        return bool(params.get('Location')) or bool(headers & {'SHOT_ZONE_BASIC', 'SHOT_ZONE_AREA'})
    if dimension == 'catch_and_shoot':
        return params.get('GeneralRange') == 'Catch and Shoot'
    return False


def validate(ledger, review, root, phase='final'):
    issues = []
    root = Path(root).resolve()
    def fail(code, where, message):
        issues.append(dict(code=code, where=where, message=message))
    def refs(items, where):
        result = []
        if not isinstance(items, list) or not items:
            fail('source_missing', where, 'Supply actual file references and SHA256, not a label.')
            return result
        for ref in items:
            try:
                path = (root / ref['path']).resolve()
                if not path.is_relative_to(root):
                    raise ValueError('Reference escapes evidence root')
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != ref['sha256']:
                    raise ValueError('Source hash mismatch')
                result.append(path)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                fail('source_invalid', where, str(exc))
        return result
    if not isinstance(ledger, list) or not isinstance(review, dict):
        return [dict(code='schema', where='root', message='Ledger list and review object required.')]
    try:
        date.fromisoformat(review['slate_date'])
        cutoff = review['cutoff']
        if date.fromisoformat(cutoff) >= date.fromisoformat(review['slate_date']):
            raise ValueError('Cutoff must precede slate date')
    except (KeyError, TypeError, ValueError) as exc:
        fail('date', 'review', str(exc))
        cutoff = ''
    if review.get('weights') != dict(core=92.5, creation=5, oreb_max=2.5):
        fail('weights', 'review', 'Preserve 92.5/5/max2.5 judgment allowances; no new score.')
    expected = review.get('expected_candidates', [])
    if not isinstance(expected, list) or not expected or not all(text(c) for c in expected) or len(set(expected)) != len(expected):
        fail('candidates', 'review', 'Explicit unique slate directions required.')
        expected = []
    countercases = review.get('countercases', {})
    dimensions = review.get('exploited_dimensions', {})
    if not isinstance(countercases, dict) or not isinstance(dimensions, dict):
        fail('schema', 'review', 'Countercases and exploited_dimensions must be objects.')
        countercases, dimensions = {}, {}
    index, normalized, last_stage = {}, {}, 0
    for i, row in enumerate(ledger):
        where = f'ledger[{i}]'
        if not isinstance(row, dict):
            fail('schema', where, 'Row must be an object.'); continue
        stage, candidate = row.get('stage'), row.get('candidate')
        if type(stage) is not int or stage not in (1, 2, 3, 4) or not text(candidate):
            fail('stage', where, 'Stages 1-4 and candidate required.'); continue
        if stage < last_stage:
            fail('order', where, 'Ledger must be accumulated in pass order.')
        last_stage = stage
        key = (candidate, stage)
        if key in index:
            fail('duplicate', where, 'Duplicate candidate/pass.')
        index[key] = row
        previous = index.get((candidate, stage-1))
        decision, execution = row.get('decision'), row.get('execution')
        if decision not in ('Advance', 'Watchlist', 'Reject'):
            fail('decision', where, 'Explicit decision required.')
        if row.get('cutoff') != cutoff:
            fail('cutoff', where, 'Row cutoff must equal the review cutoff.')
        if execution == 'not_applicable':
            if not previous or previous.get('decision') != 'Reject' or decision != 'Reject' or not text(row.get('reason')):
                fail('skip', where, 'Only explicitly rejected cores may be skipped with a reason.')
            continue
        if execution not in ('completed', 'partial', 'blocked'):
            fail('execution', where, 'Do not call a skipped or missing pass completed.')
        if execution in ('partial', 'blocked') and not text(row.get('missing')):
            fail('missing', where, 'State missing evidence and its consequence.')
        if not isinstance(row.get('figures'), dict) or not row['figures']:
            fail('figures', where, 'Actual figures required.')
        refs(row.get('source_refs'), where)
        for field in ('reason', 'offense_strength', 'defensive_concession', 'strongest_contradiction'):
            if not text(row.get(field)):
                fail('reasoning', where, f'Missing {field}.')
        if decision != 'Reject' and stage in (3, 4):
            reason = re.sub(r'\s+', ' ', str(row.get('reason', '')).strip().casefold())
            normalized.setdefault((stage, reason), []).append(candidate)
            comp = row.get('comparison', {})
            if not isinstance(comp, dict) or not all(number(comp.get(k)) for k in ('offense_baseline', 'defense_concession')) or not all(text(comp.get(k)) for k in ('units', 'window', 'incremental_effect')):
                fail('comparison', where, 'Supply baseline versus concession, units/window and incremental interpretation.')
            dr = row.get('decision_review', {})
            if not isinstance(dr, dict) or not previous or dr.get('previous') != previous.get('decision') or dr.get('current') != decision or dr.get('effect') not in ('strengthens', 'weakens', 'neutral', 'unresolved') or not text(dr.get('rationale')):
                fail('decision_review', where, 'Explicit fresh review required; unchanged decisions are legitimate, automatic carry-forward is not.')
    for (stage, reason), candidates in normalized.items():
        if len(candidates) > 1:
            fail('boilerplate', f'pass{stage}', f'Identical reasoning across live candidates: {candidates}')
    if set(index) != {(c, s) for c in expected for s in (1, 2, 3, 4)}:
        fail('coverage', 'ledger', 'Every declared slate direction needs four unique pass entries.')
    finals = review.get('final_decisions', {})
    if not isinstance(finals, dict) or set(finals) != set(expected) or any(v not in ('Advance', 'Watchlist', 'Reject') for v in finals.values()):
        fail('final_decisions', 'review', 'Record final post-availability decision for every direction.'); finals = {}
    finalists = review.get('finalists', [])
    if not isinstance(finalists, list) or len(finalists) > 3 or len(set(finalists)) != len(finalists):
        fail('finalists', 'review', 'Up to three unique finalists, including zero.'); finalists = []
    for candidate in finalists:
        if finals.get(candidate) != 'Advance':
            fail('finalist_status', candidate, 'Only final Advance candidates qualify.')
        case = countercases.get(candidate, {})
        if phase == 'draft':
            continue
        if not isinstance(case, dict) or not all(text(case.get(k)) for k in ('reject_case', 'response')):
            fail('countercase', candidate, 'Auditor must argue rejection of this finalist and answer it.')
        else:
            refs(case.get('source_refs'), candidate)
    watch = [c for c, d in finals.items() if d == 'Watchlist']
    alternative = review.get('watchlist_challenge', {})
    if phase == 'final' and watch and (not isinstance(alternative, dict) or alternative.get('candidate') not in watch or not all(text(alternative.get(k)) for k in ('promotion_case', 'response'))):
        fail('watchlist_challenge', 'review', 'Challenge exclusion of the strongest Watchlist alternative.')
    if phase == 'final' and watch and isinstance(alternative, dict):
        refs(alternative.get('source_refs'), 'watchlist_challenge')
    players = review.get('players', [])
    if not isinstance(players, list):
        fail('players', 'review', 'Players must be a list.'); players = []
    for i, player in enumerate(players):
        where = f'players[{i}]'
        if not isinstance(player, dict):
            fail('schema', where, 'Player object required.'); continue
        if player.get('candidate') not in finalists:
            fail('player_rescue', where, 'A player cannot rescue an unqualified team.')
        fits = player.get('fits', [])
        required = dimensions.get(player.get('candidate'), [])
        if not isinstance(required, list) or not required or not all(text(d) for d in required) or not isinstance(fits, list) or not all(isinstance(f, dict) for f in fits) or {f.get('dimension') for f in fits} != set(required):
            fail('fit_coverage', where, 'Explicit fit status for every claimed defensive dimension required.'); fits = []
        for fit in fits:
            status = fit.get('status')
            if status == 'verified':
                paths = refs(fit.get('source_refs'), where)
                try:
                    games = fit.get('game_ids', [])
                    if fit.get('coverage') != 'matched' or len(set(paths)) < 2 or not all(has_dimension(load(path), fit.get('dimension')) for path in paths):
                        raise ValueError('Source does not measure claimed dimension with matched coverage.')
                    if not isinstance(games, list) or not games or not all(text(g) for g in games) or len(set(games)) != len(games) or not all(number(fit.get(k)) for k in ('offense_value', 'defense_value')) or not all(text(fit.get(k)) for k in ('units', 'window')):
                        raise ValueError('Verified fit requires paired figures, units/window and matched game IDs.')
                except (OSError, ValueError, TypeError, AttributeError) as exc:
                    fail('fit_dimension', where, str(exc))
            elif status in ('partial', 'unverified'):
                if fit.get('boost_claimed') is not False or not text(fit.get('limitation')):
                    fail('fit_uncertainty', where, 'Unverified/partial fit needs visible limitation and no measured-fit boost.')
            else:
                fail('fit_status', where, 'Fit must be verified, partial or unverified.')
        comparisons = player.get('rotation_comparables', [])
        if not isinstance(comparisons, list) or not comparisons:
            fail('rotation_missing', where, 'Comparable participation table required.'); comparisons = []
        for comp in comparisons:
            try:
                paths = refs([comp['source_ref']], where)
                if not paths: continue
                actual = comparable(load(paths[0]), comp['team'], player['player_id'], cutoff, comp.get('present', []), comp.get('absent', []))
                if comp.get('summary') != actual:
                    fail('rotation_mismatch', where, 'Recomputed comparable counts/minutes/attempts differ.')
                if not text(comp.get('sample_caveat')) or not text(comp.get('chosen_adjustment')):
                    fail('rotation_reasoning', where, 'Explain confounding/sample limits and chosen range adjustment.')
            except (KeyError, TypeError, ValueError, OSError) as exc:
                fail('rotation_invalid', where, str(exc))
        baseline = player.get('conversion_baseline', {})
        if not isinstance(baseline, dict) or not number(baseline.get('made')) or not number(baseline.get('attempts')) or not 0 <= baseline['made'] <= baseline['attempts'] or baseline['attempts'] <= 0 or not all(text(baseline.get(k)) for k in ('window', 'selection_reason')):
            fail('conversion', where, 'Declare actual conversion baseline and why it was chosen.')
        else:
            refs(baseline.get('source_refs'), where)
        if player.get('range_label') != 'judgment_band' or not text(player.get('range_reason')):
            fail('range_reasoning', where, 'Explain judgment bands; no unvalidated confidence-interval claim.')
        for field in ('minutes_band', 'attempts_band', 'conservative_makes_band', 'stretch_makes_band'):
            band = player.get(field)
            if not isinstance(band, list) or len(band) != 2 or not all(number(x) for x in band) or not 0 <= band[0] <= band[1]:
                fail('range_bounds', where, f'Invalid or missing {field}.')
    if set(finalists) != {p.get('candidate') for p in players if isinstance(p, dict)}:
        fail('player_coverage', 'review', 'Each finalist needs player review; remove unsupported finalists rather than fill quotas.')
    audit = review.get('audit', {})
    if phase == 'final' and (not isinstance(audit, dict) or not all(audit.get(k) == 'accepted' for k in ('data', 'reasoning'))):
        fail('audit_incomplete', 'review', 'Separate data and reasoning verdicts must both be accepted for approved output.')
    if phase == 'final' and (not isinstance(audit, dict) or audit.get('publication') not in ('verified', 'not_checked', 'blocked') or audit.get('visual') not in ('verified', 'not_checked', 'blocked')):
        fail('audit_scope', 'review', 'Explicit publication and visual scope required; arithmetic is not publication approval.')
    if phase == 'final' and isinstance(audit, dict):
        refs(audit.get('source_refs'), 'audit')
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--phase', choices=['draft', 'final'], default='final')
    args = parser.parse_args()
    try:
        issues = validate(load(args.ledger), load(args.review), args.root, args.phase)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        issues = [dict(code='input', where='root', message=str(exc))]
    print(json.dumps(dict(structural_checks_passed=not issues, issues=issues,
                          limitation='Does not certify source truth, prose quality, forecast calibration or actual agent attention.')))
    return 2 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())
