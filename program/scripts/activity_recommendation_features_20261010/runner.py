"""Exploratory Noul features plus code ranking; original retest stays frozen.

Importing this module never imports a provider SDK or reads credentials. Only
the root-operated CLI creates the existing paid Providers client. Unit tests
inject a cost-free call double into rank_features().
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FROZEN = ROOT / 'program/scripts/activity_recommendation_retest'
PLAN = ROOT / 'program/research/activity_recommendation_20261009/retest-feature-addon-20261010.md'
VERSION = 'noul-binary-features-v1'
CHUNK_SIZE = 64
THRESHOLD = 0.5


def _no_oracle(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.startswith('oracle_') or key in ('gold', 'expected', 'labels', 'score', 'ranked_ids', 'gold_score_groups'):
                raise ValueError('oracle_or_gold_in_public_input')
            _no_oracle(child)
    elif isinstance(value, list):
        for child in value:
            _no_oracle(child)


def _number(value, label, maximum=None):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum):
        raise ValueError('invalid_' + label)
    return value


def build_questions(public):
    """Ask each distinct trait once per candidate, without customer weights."""
    _no_oracle(public)
    prefs = public['customer']['preferences']
    traits = []
    for pref in prefs['likes'] + prefs['dislikes']:
        trait = pref['trait']
        if not isinstance(trait, str) or not trait.strip():
            raise ValueError('invalid_trait')
        if trait not in traits:
            traits.append(trait)
    if not traits:
        raise ValueError('no_traits')
    questions = {}
    bindings = {}
    seen = set()
    for candidate_index, candidate in enumerate(public['candidates']):
        cid = candidate['id']
        if not isinstance(cid, str) or not cid.strip() or cid in seen:
            raise ValueError('invalid_or_duplicate_candidate_id')
        seen.add(cid)
        description = candidate['description']
        if not isinstance(description, str) or not description.strip():
            raise ValueError('invalid_description')
        for trait_index, trait in enumerate(traits):
            key = f'q{candidate_index:04d}_t{trait_index:03d}'
            questions[key] = {
                'type': 'noul',
                'instructions': {'question': f'이 설명이 [{trait}] 성격을 실제 제공함을 말하는가?',
                                 'description': description},
                'criteria': {'true': '설명에서 해당 성격이나 경험을 실제로 제공한다고 확인할 수 있음',
                             'false': '부정, 단순 인용, 명령, 광고성 지시 또는 비제공이며 실제 제공 근거가 없음'},
            }
            bindings[key] = (cid, trait)
    return questions, bindings


def parse_noul(raw, expected):
    answers = raw['answers']
    if not isinstance(answers, dict) or set(answers) != set(expected):
        raise ValueError('missing_or_extra_features')
    probabilities = {}
    for key, answer in answers.items():
        if not isinstance(answer, dict) or answer.get('type') != 'noul':
            raise ValueError('invalid_feature_type')
        probabilities[key] = _number(answer['noul'], 'noul', maximum=1)
    return {'probabilities': probabilities}


def code_rank(public, decisions):
    """Boolean provision -> weighted taste -> quarter grade -> utility."""
    prefs = public['customer']['preferences']
    weights = public['weights']
    for name in ('taste', 'travel', 'similarity'):
        _number(weights[name], 'weight', maximum=1)
    if not math.isclose(sum(weights.values()), 1, abs_tol=1e-9, rel_tol=0):
        raise ValueError('invalid_weight_sum')
    scores = {}
    for candidate in public['candidates']:
        cid = candidate['id']
        positive = sum(_number(p['importance'], 'importance') for p in prefs['likes'] if decisions[cid][p['trait']])
        negative = sum(_number(p['penalty'], 'penalty') for p in prefs['dislikes'] if decisions[cid][p['trait']])
        clipped = min(1, max(0, positive - negative))
        grade = math.floor(clipped * 4 + 0.5) / 4
        travel = _number(candidate['facts']['travel_min']['value'], 'travel')
        similarity = 1 if candidate['category'] == public['origin']['category'] else (0.5 if candidate['category'] == '복합문화' else 0)
        utility = weights['taste'] * grade + weights['travel'] * max(0, 1 - travel / 60) + weights['similarity'] * similarity
        scores[cid] = {'taste_positive': positive, 'taste_penalty': negative, 'taste_clipped': clipped,
                       'taste_grade': grade, 'travel_score': max(0, 1 - travel / 60),
                       'similarity': similarity, 'utility': utility}
    ranking = sorted(scores, key=lambda cid: (-scores[cid]['utility'], cid))
    return ranking[:min(3, len(ranking))], scores


def rank_features(public, provider, model='jev-latest'):
    """Use an injected existing Providers.call; never falls back to a model."""
    _no_oracle(public)
    candidates = public['candidates']
    common = {'feature_method': VERSION, 'threshold': THRESHOLD, 'chunk_size': CHUNK_SIZE,
              'requested_model': model, 'semantic_factuality_verified': False,
              'human_review_count': 0, 'evidence_quotes_generated': False}
    if len(candidates) <= 1:
        return {**common, 'status': 'ok', 'ranking': [c['id'] for c in candidates],
                'cost_usd': 0.0, 'latency_ms': 0.0, 'call_ids': [], 'subcalls': [],
                'feature_probabilities': {}, 'feature_decisions': {}, 'code_scores': {},
                'model': 'code_single_candidate' if candidates else 'code_empty_pool',
                'bypassed_single_candidate': len(candidates) == 1}
    questions, bindings = build_questions(public)
    items = list(questions.items())
    parts = []
    probabilities = {c['id']: {} for c in candidates}
    decisions = {c['id']: {} for c in candidates}
    failure = None
    for offset in range(0, len(items), CHUNK_SIZE):
        chunk = dict(items[offset:offset + CHUNK_SIZE])
        request = {'model': model, 'state': {}, 'questions': chunk}
        try:
            part = provider.call('jev', request, lambda raw, expected=set(chunk): parse_noul(raw, expected))
        except RuntimeError as error:
            # Existing reserve raises before sending; already paid chunks stay in
            # this case's cost and IDs even when the next reservation is refused.
            if type(error).__name__ not in ('BudgetExceeded', 'BudgetLocked'):
                raise
            failure = {'status': 'budget_stopped', 'error_type': type(error).__name__}
            break
        parts.append(part)
        if part['status'] != 'ok':
            failure = {'status': 'failed', 'error_type': part.get('error_type'),
                       'validation_error': part.get('validation_error')}
            break
        for key, probability in part['probabilities'].items():
            cid, trait = bindings[key]
            probabilities[cid][trait] = probability
            decisions[cid][trait] = probability >= THRESHOLD
    ranking, scores = ([], {}) if failure else code_rank(public, decisions)
    models = list(dict.fromkeys(p.get('model') for p in parts if p.get('model') is not None))
    return {**common, 'status': 'ok' if failure is None else failure['status'],
            'ranking': ranking, 'feature_probabilities': probabilities,
            'feature_decisions': decisions, 'code_scores': scores,
            'question_count': len(questions), 'completed_questions': sum(len(v) for v in probabilities.values()),
            'cost_usd': sum(p['cost_usd'] for p in parts),
            'latency_ms': sum(p['latency_ms'] for p in parts),
            'call_ids': [cid for part in parts for cid in part['call_ids']],
            'model': models[-1] if models else None, 'returned_models': models, 'subcalls': parts,
            'failure': failure}


def work_items(cases, stage, seed, prepare_case, variant):
    if stage == 'eval':
        work = [(case, 'main', {}) for case in cases]
    elif stage == 'stability':
        ready = sorted([c for c in cases if prepare_case(c)['status'] == 'ready' and len(c['candidates']) <= 16], key=lambda c: c['case_id'])[:8]
        work = []
        for index, case in enumerate(ready):
            for offset in (0, 1):
                changed, condition, inverse = variant(case, index * 2 + offset)
                work.append((changed, condition, inverse))
    else:
        raise ValueError('stage_must_be_eval_or_stability')
    random.Random(seed).shuffle(work)
    return work


def _save_new(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def run(args):
    if not re.fullmatch(r'features-[A-Za-z0-9][A-Za-z0-9_.-]*', args.run_id):
        raise ValueError('run_id_must_start_features_and_be_a_single_name')
    # Root-only execution path. These frozen imports do not access credentials;
    # the Providers constructor below is the single credential read boundary.
    sys.path.insert(0, str(FROZEN))
    from budget import Budget
    from fixtures import prepare_case, public_case
    from providers import CONFIG, Providers
    from run import root_metrics, variant

    data = ROOT / CONFIG['dataset_directory']
    source = data / CONFIG['raw_subdirectory'] / 'eval.jsonl'
    cases = [json.loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
    work = work_items(cases, args.stage, CONFIG['seed'], prepare_case, variant)
    budget = Budget(data / 'ledger.sqlite', CONFIG['new_budget_usd'], CONFIG['max_paid_calls'], CONFIG['baseline_usd'])
    with budget.run_lock():
        directory = data / 'runs' / args.run_id
        directory.mkdir(parents=True, exist_ok=False)
        frozen_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in FROZEN.glob('*.py')}
        own_hashes = {'runner.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        _save_new(directory / 'metadata.json', {
            'stage': args.stage, 'method': VERSION, 'exploratory_addon': True,
            'same_model_selection_as_main': False, 'threshold': THRESHOLD, 'chunk_size': CHUNK_SIZE,
            'config': CONFIG, 'source_hashes': frozen_hashes, 'frozen_source_hashes': frozen_hashes, 'addon_source_hashes': own_hashes,
            'dataset_hash': hashlib.sha256(source.read_bytes()).hexdigest(),
            'preregistration_hash': hashlib.sha256(PLAN.read_bytes()).hexdigest(),
            'planned_cases': len(work), 'human_reviews': 0, 'tools': [], 'auto_retries': 0,
            'same_shared_budget_and_call_limit': True, 'started_at': datetime.now(timezone.utc).isoformat()})
        _save_new(directory / 'schedule.json', [{'case_id': c['case_id'], 'condition': condition,
                   'identity_inverse': inverse} for c, condition, inverse in work])
        provider = Providers(budget, directory)
        completed = 0
        stop = None
        try:
            for case, condition, inverse in work:
                prepared = prepare_case(case)
                state = prepared['status']
                if state == 'ready':
                    public = public_case(case, prepared['feasible_ids'])
                    result = rank_features(public, provider, CONFIG['models']['jev'])
                else:
                    result = {'status': 'ok', 'decision_status': state, 'ranking': [],
                              'cost_usd': 0.0, 'latency_ms': 0.0, 'call_ids': [], 'subcalls': [],
                              'model': 'code_state_gate', 'feature_probabilities': {}, 'feature_decisions': {},
                              'semantic_factuality_verified': False, 'human_review_count': 0,
                              'evidence_quotes_generated': False}
                row = {'case_id': case['case_id'], 'base_id': case['base_id'], 'split': case['split'],
                       'stratum': case['stratum'], 'condition': condition, 'identity_inverse': inverse,
                       'arm': 'jev_noul_features_code', 'decision_status': state,
                       'eligible_count': len(prepared['feasible_ids']), **result,
                       'metrics': root_metrics(case, result)}
                with (directory / 'results.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                    stream.flush()
                completed += 1
                print(json.dumps({'stage': args.stage, 'completed': completed, 'planned': len(work), 'budget': budget.snapshot()}, ensure_ascii=True), flush=True)
                if result['status'] == 'budget_stopped':
                    stop = result['failure']['error_type']
                    break
        except BaseException as error:
            stop = type(error).__name__
            raise
        finally:
            _save_new(directory / 'finish.json', {
                'completed': completed, 'planned': len(work), 'stop': stop, 'budget': budget.snapshot(),
                'finished_at': datetime.now(timezone.utc).isoformat(),
                'source_hashes_unchanged': frozen_hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in FROZEN.glob('*.py')},
                'frozen_source_hashes_unchanged': frozen_hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in FROZEN.glob('*.py')},
                'addon_source_hashes_unchanged': own_hashes == {'runner.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=('eval', 'stability'), required=True)
    parser.add_argument('--run-id', required=True)
    run(parser.parse_args())
