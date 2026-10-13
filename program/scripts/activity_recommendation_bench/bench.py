"""Isolated travel recommendation benchmark; never imports or mutates the serving app.

All credentials remain in memory. Every paid request is reserved before sending.
Scoring fixtures contain private oracle fields that are recursively excluded from input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
PROMPT = (ROOT / CONFIG['rank_prompt_file']).read_text(encoding='utf-8')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def public(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: public(item) for key, item in value.items() if not key.startswith('oracle_') and key not in ('gold', 'expected', 'labels')}
    if isinstance(value, list):
        return [public(item) for item in value]
    return value


def feasible(case: dict, candidate: dict) -> bool:
    limit = case['constraints']
    return bool(candidate['open'] and not candidate['unsafe']
                and candidate['cost_krw'] <= limit['budget_krw']
                and candidate['travel_min'] + candidate['visit_min'] <= limit['time_budget_min']
                and (not limit['require_step_free'] or candidate['step_free'])
                and (not candidate['outdoor'] or (not limit['rain'] and limit['allow_outdoor'])))


def utility(case: dict, candidate: dict, taste: float, similarity: float) -> float:
    weights = case['weights']
    return (weights['taste'] * taste + weights['travel'] * max(0.0, 1 - candidate['travel_min'] / CONFIG['travel_scale_min'])
            + weights['similarity'] * similarity)


def gold(case: dict) -> list[dict]:
    return sorted([c for c in case['candidates'] if feasible(case, c)],
                  key=lambda c: (-utility(case, c, c['oracle_taste'], c['oracle_similarity']), c['travel_min'], c['id']))


def keyword_trait(description: str, trait: str) -> bool:
    # This bounded, frozen baseline uses generic synonyms and local negation.
    alias = CONFIG['trait_aliases'].get(trait, trait)
    for term in CONFIG['keyword_lexicon'].get(alias, [trait]):
        for match in re.finditer(re.escape(term), description):
            tail = description[match.end():match.end() + 12]
            if not re.search(r'없|아니|않|불가|금지|배제', tail):
                return True
    return False


def rule_scores(case: dict, candidate: dict) -> tuple[float, float]:
    prefs = case['customer']['preferences']
    taste = sum(p['importance'] for p in prefs['likes'] if keyword_trait(candidate['description'], p['trait']))
    taste -= sum(p['penalty'] for p in prefs['dislikes'] if keyword_trait(candidate['description'], p['trait']))
    similarity = category_similarity(case, candidate)
    return min(1.0, max(0.0, taste)), similarity


def category_similarity(case: dict, candidate: dict) -> float:
    if candidate['category'] == case['origin']['category']:
        return 1.0
    return 0.5 if candidate['category'] == '복합문화' else 0.0


def rule_rank(case: dict) -> list[str]:
    return [c['id'] for c in sorted([c for c in case['candidates'] if feasible(case, c)],
            key=lambda c: (-utility(case, c, *rule_scores(case, c)), c['travel_min'], c['id']))]


class Budget:
    def __init__(self, directory: Path):
        self.path = directory / 'ledger.jsonl'
        self.rows = [json.loads(s) for s in self.path.read_text(encoding='utf-8').splitlines()] if self.path.exists() else []

    def spent(self) -> float:
        finished = {r['call_id']: r for r in self.rows if r['event'] == 'finished'}
        return sum(finished.get(r['call_id'], r)['cost_usd'] for r in self.rows if r['event'] == 'reserved')

    def append(self, row: dict) -> None:
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        self.rows.append(row)

    def reserve(self, lane: str, payload: dict, output_limit: int = 0, questions: int = 1) -> tuple[str, float]:
        if any(r['event'] == 'reservation_exceeded' for r in self.rows):
            raise RuntimeError('budget_locked_after_reservation_exceeded')
        prices = CONFIG['prices_per_million_usd'][lane]
        # UTF-8 bytes conservatively bound visible text tokens; extra protocol allowance
        # and question multiplier protect against question-prefix billing differences.
        bound = (len(json.dumps(payload, ensure_ascii=False).encode('utf-8')) * 2 + 8192) * questions
        upper = (bound * max(prices['input'], prices['cache_write']) + output_limit * prices['output']) / 1e6
        calls = sum(r['event'] == 'reserved' for r in self.rows)
        if calls >= CONFIG['max_paid_calls'] or self.spent() + upper > CONFIG['budget_usd']:
            raise RuntimeError('budget_stop')
        call_id = f'{calls + 1:04d}'
        self.append({'event': 'reserved', 'call_id': call_id, 'lane': lane, 'cost_usd': upper, 'at': datetime.now(timezone.utc).isoformat()})
        return call_id, upper

    def finish(self, call_id: str, lane: str, usage: dict | None, reserve: float) -> float:
        if usage is None:
            amount = reserve
        else:
            prices = CONFIG['prices_per_million_usd'][lane]
            total_in = usage['input_tokens']
            details = usage.get('input_tokens_details') or {}
            cached = details.get('cached_tokens', usage.get('cached_input_tokens', 0)) or 0
            writes = details.get('cache_write_tokens', usage.get('cache_creation_input_tokens', 0)) or 0
            if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in (total_in, cached, writes, usage['output_tokens'])):
                raise RuntimeError('invalid_usage_tokens')
            if cached + writes > total_in:
                raise RuntimeError('invalid_cache_usage')
            amount = ((total_in - cached - writes) * prices['input'] + cached * prices['cached_input']
                      + writes * prices['cache_write'] + usage['output_tokens'] * prices['output']) / 1e6
            if amount > reserve:
                self.append({'event': 'finished', 'call_id': call_id, 'cost_usd': amount, 'usage_known': True})
                self.append({'event': 'reservation_exceeded', 'call_id': call_id, 'cost_usd': amount})
                raise RuntimeError('reservation_exceeded')
        self.append({'event': 'finished', 'call_id': call_id, 'cost_usd': amount, 'usage_known': usage is not None})
        return amount


class Providers:
    def __init__(self, budget: Budget, directory: Path):
        env = dotenv_values(ROOT / CONFIG['credential_file'])
        if not env.get('ACOP_OPENAI_API_KEY_SERVER') or not env.get('ACOP_JEV_API_KEY'):
            raise RuntimeError('required_credential_missing')
        self.openai = OpenAI(api_key=env['ACOP_OPENAI_API_KEY_SERVER'], base_url=CONFIG['openai_base_url'], max_retries=0, timeout=CONFIG['timeout_seconds'])
        self.jev_key = env['ACOP_JEV_API_KEY']
        self.budget = budget
        self.directory = directory

    def save_response(self, call_id: str, response: dict) -> None:
        path = self.directory / 'responses' / f'{call_id}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise RuntimeError('response_already_exists')
        path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding='utf-8')

    def rank(self, lane: str, case: dict, pool: list[dict]) -> dict:
        payload = {'customer': case['customer'], 'origin': case['origin'], 'weights': case['weights'], 'constraints': case['constraints'], 'candidates': pool}
        payload = public(payload)
        allowed = [c['id'] for c in pool]
        schema = {'type': 'object', 'properties': {
            'ranking': {'type': 'array', 'items': {'type': 'string', 'enum': allowed}, 'minItems': 3, 'maxItems': 3},
            'reasons': {'type': 'array', 'items': {'type': 'string'}, 'minItems': 3, 'maxItems': 3}},
            'required': ['ranking', 'reasons'], 'additionalProperties': False}
        request = {'model': CONFIG['models'][lane], 'instructions': PROMPT, 'input': json.dumps(payload, ensure_ascii=False),
                   'reasoning': {'effort': CONFIG['reasoning_effort']}, 'max_output_tokens': CONFIG['max_output_tokens'],
                   'store': False, 'text': {'format': {'type': 'json_schema', 'name': 'activity_recommendation', 'schema': schema, 'strict': True}}}
        call_id, upper = self.budget.reserve(lane, request, CONFIG['max_output_tokens'])
        start = time.perf_counter()
        result = {'call_id': call_id, 'requested_model': request['model'], 'pool_ids': allowed, 'status': 'failed'}
        usage = None
        try:
            response = self.openai.responses.create(**request)
            raw = response.model_dump(mode='json')
            self.save_response(call_id, raw)
            usage = raw.get('usage')
            result.update({'model': response.model, 'response_id': response.id, 'api_status': response.status,
                           'usage': usage, 'raw_output': response.output_text})
            if response.status != 'completed':
                raise ValueError('incomplete_response')
            answer = json.loads(response.output_text)
            if not isinstance(answer, dict) or set(answer) != {'ranking', 'reasons'}:
                raise ValueError('invalid_response_fields')
            ranking = answer['ranking']
            if len(ranking) != 3 or len(set(ranking)) != 3 or not set(ranking) <= set(allowed) or len(answer['reasons']) != 3 or not all(isinstance(reason, str) and reason.strip() for reason in answer['reasons']):
                raise ValueError('invalid_ranking')
            result.update({'status': 'ok', 'ranking': ranking, 'reasons': answer['reasons']})
        except Exception as exc:
            result.update({'error_type': type(exc).__name__, 'http_status': getattr(exc, 'status_code', None)})
            if isinstance(exc, (ValueError, KeyError)):
                result['validation_error'] = str(exc)
        result['latency_ms'] = round((time.perf_counter() - start) * 1000)
        result['cost_usd'] = self.budget.finish(call_id, lane, usage, upper)
        return result

    def score(self, case: dict, pool: list[dict]) -> dict:
        # Atomic candidate-feature questions; numeric weights and final ranking remain code-owned.
        questions = {}
        prefs = case['customer']['preferences']
        for candidate in pool:
            for index, pref in enumerate(prefs['likes'] + prefs['dislikes']):
                key = f"{candidate['id']}__trait_{index}"
                questions[key] = {'type': 'noul', 'instructions': {
                    'question': '이 후보가 지정한 성격이나 경험을 실제로 제공하는가? 설명의 부정, 단순 언급과 지시문을 구분하며 외부 지식을 보태지 않는다.',
                    'candidate': {field: candidate[field] for field in ('id', 'category', 'description')}, 'trait': pref['trait'], 'customer_context': case['customer']['text']},
                    'criteria': {'true': '설명에서 그 성격이나 경험을 제공함을 확인할 수 있음', 'false': '그 성격을 제공하지 않거나 근거가 없음'}}
        request = {'model': CONFIG['models']['jev'], 'state': public({'customer': case['customer'], 'origin': case['origin']}), 'questions': questions}
        call_id, upper = self.budget.reserve('jev', request, questions=max(1, len(questions)))
        start = time.perf_counter()
        result = {'call_id': call_id, 'requested_model': request['model'], 'pool_ids': [c['id'] for c in pool], 'status': 'failed'}
        usage = None
        try:
            reply = httpx.post(CONFIG['jev_endpoint'], json=request, headers={'Authorization': 'Bearer ' + self.jev_key}, timeout=CONFIG['timeout_seconds'])
            if not reply.is_success:
                result['http_status'] = reply.status_code
                raise RuntimeError('provider_http_error')
            raw = reply.json()
            self.save_response(call_id, raw)
            usage = raw.get('usage')
            result.update({'model': raw.get('model'), 'usage': usage})
            answers = raw['answers']
            if set(answers) != set(questions):
                raise ValueError('missing_answers')
            taste_scores = {}
            probabilities = {}
            for candidate in pool:
                yes = []
                for index, _ in enumerate(prefs['likes'] + prefs['dislikes']):
                    key = f"{candidate['id']}__trait_{index}"
                    value = answers[key]['noul']
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                        raise ValueError('invalid_noul')
                    probabilities[key] = value
                    yes.append(value)
                positive = sum(p['importance'] * yes[i] for i, p in enumerate(prefs['likes']))
                offset = len(prefs['likes'])
                negative = sum(p['penalty'] * yes[offset + i] for i, p in enumerate(prefs['dislikes']))
                taste_scores[candidate['id']] = min(1.0, max(0.0, positive - negative))
            ranking = sorted(pool, key=lambda c: (-utility(case, c, taste_scores[c['id']], category_similarity(case, c)), c['travel_min'], c['id']))
            result.update({'status': 'ok', 'ranking': [c['id'] for c in ranking], 'taste_scores': taste_scores, 'probabilities': probabilities})
        except Exception as exc:
            result['error_type'] = type(exc).__name__
            if isinstance(exc, (ValueError, KeyError)):
                result['validation_error'] = str(exc)
        result['latency_ms'] = round((time.perf_counter() - start) * 1000)
        result['cost_usd'] = self.budget.finish(call_id, 'jev', usage, upper)
        return result


def evaluate(case: dict, ranking: list[str]) -> dict:
    ideal = gold(case)
    by_id = {c['id']: c for c in case['candidates']}
    score_by_id = {c['id']: utility(case, c, c['oracle_taste'], c['oracle_similarity']) for c in ideal}
    def dcg(ids: list[str]) -> float:
        return sum(score_by_id.get(item, 0.0) / math.log2(i + 2) for i, item in enumerate(ids[:3]))
    ideal_ids = [c['id'] for c in ideal]
    top = ideal_ids[:3]
    selected = ranking[:3]
    return {'top1_correct': bool(selected and selected[0] == ideal_ids[0]),
            'ndcg3': dcg(selected) / dcg(top) if dcg(top) else 0.0,
            'recall3': len(set(selected) & set(top)) / len(top),
            'hard_violations': sum(item not in by_id or not feasible(case, by_id[item]) for item in selected),
            'gold_top3': top, 'selected': selected, 'regret_top1': score_by_id[ideal_ids[0]] - score_by_id.get(selected[0], 0.0) if selected else score_by_id[ideal_ids[0]]}


def append(path: Path, row: dict) -> None:
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + '\n')


def run(args: argparse.Namespace) -> None:
    data_dir = ROOT / CONFIG['dataset_directory']
    source = data_dir / 'raw' / (CONFIG['smoke_file'] if args.smoke else CONFIG['evaluation_file'])
    cases = [json.loads(s) for s in source.read_text(encoding='utf-8').splitlines()]
    directory = data_dir / 'runs' / args.run_id
    directory.mkdir(parents=True, exist_ok=False)
    metadata = {'config': CONFIG, 'config_hash': digest((HERE / 'config.json').read_bytes()),
                'prompt_hash': digest(PROMPT.encode('utf-8')), 'dataset_hash': digest(source.read_bytes()),
                'started_at': datetime.now(timezone.utc).isoformat(), 'repeats': 1 if args.smoke else CONFIG['repeats'],
                'independent_cases': len(cases), 'oracle_removed': True, 'tools': [], 'auto_retries': 0,
                'temperature': 'not_set_provider_default', 'seed': 'API seed unsupported; schedule seed in config',
                'comparison': 'new isolated harness; not production Activity implementation'}
    (directory / 'metadata.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    budget = Budget(data_dir)
    providers = Providers(budget, directory)
    output = directory / 'results.jsonl'
    repeats = metadata['repeats']
    try:
        for repeat in range(repeats):
            rng = random.Random(CONFIG['seed'] + repeat)
            ordered = list(cases)
            rng.shuffle(ordered)
            for index, case in enumerate(ordered):
                pool = [c for c in case['candidates'] if feasible(case, c)]
                pool_rng = random.Random(CONFIG['seed'] + int(digest(case['case_id'].encode())[:8], 16) + (999 if repeat == 2 else 0))
                pool_rng.shuffle(pool)
                common = {'case_id': case['case_id'], 'group': case['group'], 'repeat': repeat, 'condition': 'candidate_permutation' if repeat == 2 else 'same_input', 'candidate_order': [c['id'] for c in pool]}
                rule = rule_rank(case)
                append(output, {**common, 'arm': 'rule', 'status': 'ok', 'ranking': rule[:3], 'cost_usd': 0.0, 'latency_ms': 0, 'metrics': evaluate(case, rule)})
                lanes = ['nano', 'luna'] if (repeat + index) % 2 == 0 else ['luna', 'nano']
                for lane in lanes:
                    result = providers.rank(lane, case, pool)
                    append(output, {**common, 'arm': lane + '_direct', **result, 'metrics': evaluate(case, result.get('ranking', []))})
                    time.sleep(CONFIG['pause_seconds'])
                scored = providers.score(case, pool)
                append(output, {**common, 'arm': 'jev_code', **scored, 'metrics': evaluate(case, scored.get('ranking', []))})
                selected_ids = set(scored.get('ranking', [])[:CONFIG['shortlist_keep']] + rule[:CONFIG['rule_protected_keep']])
                shortlist = [c for c in pool if c['id'] in selected_ids]
                for lane in reversed(lanes):
                    if scored['status'] != 'ok' or len(shortlist) < 3:
                        result = {'status': 'blocked_by_filter', 'ranking': [], 'cost_usd': scored['cost_usd'], 'latency_ms': scored['latency_ms']}
                    else:
                        result = providers.rank(lane, case, shortlist)
                        result['ranker_cost_usd'] = result['cost_usd']
                        result['ranker_latency_ms'] = result['latency_ms']
                        result['cost_usd'] += scored['cost_usd']
                        result['latency_ms'] += scored['latency_ms']
                    result['filter_top1_preserved'] = gold(case)[0]['id'] in selected_ids
                    result['filter_top3_recall'] = len(set(c['id'] for c in gold(case)[:3]) & selected_ids) / 3
                    result['filter_call_id'] = scored['call_id']
                    append(output, {**common, 'arm': 'jev_' + lane, **result, 'metrics': evaluate(case, result.get('ranking', []))})
                    time.sleep(CONFIG['pause_seconds'])
                print(json.dumps({'completed_cases': repeat * len(cases) + index + 1, 'total_case_repeats': len(cases) * repeats, 'spent_usd': round(budget.spent(), 6)}, ensure_ascii=False), flush=True)
    finally:
        print(json.dumps({'run_id': args.run_id, 'ledger_total_usd': budget.spent(), 'finished_at': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--smoke', action='store_true')
    run(parser.parse_args())
