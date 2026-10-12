"""Read saved study data; create a fresh audit and blinded DEVELOPMENT review pack.

No provider SDK, network, credential, production, or original-data writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import mean

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'datasets/travel/activity_recommendation_bench_20261009'
SEED = 20261010


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def public(value):
    if isinstance(value, dict):
        return {key: public(item) for key, item in value.items()
                if not key.startswith('oracle_') and key not in ('gold', 'expected', 'labels')}
    if isinstance(value, list):
        return [public(item) for item in value]
    return value


def feasible(case, candidate):
    c = case['constraints']
    return (candidate['open'] and not candidate['unsafe']
            and candidate['cost_krw'] <= c['budget_krw']
            and candidate['travel_min'] + candidate['visit_min'] <= c['time_budget_min']
            and (not c['require_step_free'] or candidate['step_free'])
            and (not candidate['outdoor'] or (not c['rain'] and c['allow_outdoor'])))


def utility(case, candidate):
    w = case['weights']
    return (w['taste'] * candidate['oracle_taste']
            + w['travel'] * max(0, 1-candidate['travel_min']/60)
            + w['similarity'] * candidate['oracle_similarity'])


def measure(case, ranking):
    pool = [c for c in case['candidates'] if feasible(case, c)]
    ideal = sorted(pool, key=lambda c: (-utility(case, c), c['travel_min'], c['id']))
    values = {c['id']: utility(case, c) for c in pool}
    top = [c['id'] for c in ideal[:3]]
    selected = ranking[:3]
    dcg = lambda ids: sum(values.get(value, 0)/math.log2(index+2) for index, value in enumerate(ids))
    return {'top1_correct': bool(selected and selected[0] == top[0]),
            'ndcg3': dcg(selected)/dcg(top),
            'recall3': len(set(selected) & set(top))/len(top)}


def estimate_cost(usage, prices, cache_mode):
    n = usage['input_tokens']
    details = usage.get('input_tokens_details') or {}
    reads = details.get('cached_tokens', usage.get('cached_input_tokens', 0)) or 0
    writes = details.get('cache_write_tokens', usage.get('cache_creation_input_tokens', 0)) or 0
    if cache_mode == 'no_cache_same_tokens':
        reads = writes = 0
    elif cache_mode == 'all_cache_read_same_tokens':
        reads, writes = n, 0
    elif cache_mode != 'observed_usage':
        raise ValueError('unknown_cache_mode')
    return ((n-reads-writes)*prices['input'] + reads*prices['cached_input']
            + writes*prices['cache_write'] + usage['output_tokens']*prices['output'])/1e6


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def run(output):
    cases = read_rows(DATA/'raw/scenarios-v2.jsonl')
    results = read_rows(DATA/'runs/main-20261009-v1/results.jsonl')
    config = json.loads((ROOT/'program/scripts/activity_recommendation_bench/config.json').read_text(encoding='utf-8'))
    case_by_id = {c['case_id']:c for c in cases}
    # Recompute saved labels, independently of the original benchmark module.
    checked = 0
    for row in results:
        ranking = row.get('ranking', []) if row['status']=='ok' else []
        actual = measure(case_by_id[row['case_id']], ranking)
        for key, value in actual.items():
            assert math.isclose(value, row['metrics'][key], abs_tol=1e-12), (row['arm'], row['case_id'], key)
        checked += 1
    controls = []
    suffixes = Counter()
    for case in cases:
        ids = sorted(c['id'] for c in case['candidates'] if feasible(case,c))
        controls.append(measure(case, ids))
        best = max((c for c in case['candidates'] if feasible(case,c)), key=lambda c:utility(case,c))
        suffixes[best['id'].rsplit('_',1)[-1]] += 1
    cost = {}
    for mode in ('observed_usage', 'no_cache_same_tokens', 'all_cache_read_same_tokens'):
        totals = Counter()
        count = Counter()
        for row in results:
            if row['arm']=='rule':
                continue
            lane = 'nano' if 'nano' in row['arm'] else 'luna' if 'luna' in row['arm'] else 'jev'
            assert row.get('usage') is not None
            # The Jev stage has no input caching in this tariff.
            own = estimate_cost(row['usage'], config['prices_per_million_usd'][lane], mode if lane!='jev' else 'observed_usage')
            if mode=='observed_usage':
                assert math.isclose(own, row.get('ranker_cost_usd',row['cost_usd']), abs_tol=1e-12)
            if row['arm'].startswith('jev_') and row['arm']!='jev_code':
                shared = next(x for x in results if x['arm']=='jev_code' and x['case_id']==row['case_id'] and x['repeat']==row['repeat'])
                own += shared['cost_usd']
            if mode=='observed_usage':
                assert math.isclose(own, row['cost_usd'], abs_tol=1e-12)
            totals[row['arm']] += own
            count[row['arm']] += 1
        cost[mode] = {arm: totals[arm]/count[arm] for arm in totals}
    ledger = read_rows(DATA/'ledger.jsonl')
    reserved = {r['call_id']:r for r in ledger if r['event']=='reserved'}
    finished = {r['call_id']:r for r in ledger if r['event']=='finished'}
    charge = sum(finished.get(call_id,row)['cost_usd'] for call_id,row in reserved.items())
    rng = random.Random(SEED)
    shuffled = list(cases)
    rng.shuffle(shuffled)
    pack = []
    mapping = []
    reviews = []
    for case in shuffled:
        review_id = 'review_'+rng.randbytes(8).hex()
        mapping_ids = {c['id']:'place_'+rng.randbytes(8).hex() for c in case['candidates']}
        shown = public(copy.deepcopy(case))
        shown.pop('group', None)
        shown['case_id'] = review_id
        for c in shown['candidates']:
            c['id'] = mapping_ids[c['id']]
            c['name'] = '평가용 가상활동 '+c['id'][-6:]
        rng.shuffle(shown['candidates'])
        pack.append(shown)
        mapping.append({'review_id':review_id, 'original_case_id':case['case_id'], 'candidate_ids':mapping_ids})
        reviews.append({'case_id':review_id,'reviewers':[
            {'reviewer_id':None,'is_human':None,'reviewed_at':None,'trait_annotations':{},'preferred_top3':[],
             'acceptable_ties':[],'evidence_notes':{},'status':'pending'} for _ in range(2)],'adjudication':None})
    output.mkdir(parents=True, exist_ok=False)
    review_dir = output/'human-review-development'
    review_dir.mkdir()
    write(review_dir/'cases.json', pack)
    write(review_dir/'labels.blank.json', reviews)
    write(output/'review-id-map.private.json', mapping)
    report = {'source_study':'main-20261009-v1','seed':SEED,'paid_api_calls':0,
              'recomputed_metric_rows':checked, 'case_count':len(cases),
              'gold_top1_id_suffix_counts':dict(suffixes),
              'id_only_control': {'top1_hits':sum(x['top1_correct'] for x in controls),
                                  'denominator':len(controls), 'ndcg3_mean':mean(x['ndcg3'] for x in controls),
                                  'recall3_mean':mean(x['recall3'] for x in controls)},
              'cost_sensitivity_usd_per_path':cost,
              'cost_sensitivity_is_counterfactual':True,
              'existing_study_budget':{'paid_calls':len(reserved),'max_paid_calls':config['max_paid_calls'],
                                       'usage_based_usd':charge,'budget_usd':config['budget_usd'],
                                       'available_call_slots':max(0,config['max_paid_calls']-len(reserved))},
              'human_review':{'development_cases_prepared':len(pack),'planned_reviews':len(pack)*2,
                              'completed_human_reviews':0,'previously_used_by_models':True,'holdout':False},
              'original_fixture_sha256':hashlib.sha256((DATA/'raw/scenarios-v2.jsonl').read_bytes()).hexdigest()}
    write(output/'audit.json', report)
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    run(parser.parse_args().output_dir)
