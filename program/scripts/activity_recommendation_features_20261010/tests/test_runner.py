"""Cost-free doubles exercise atomic-feature composition, never provider APIs."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from runner import build_questions, parse_noul, code_rank, rank_features, work_items


def public_fixture(count=2):
    return {'case_id': 'synthetic', 'customer': {'text': '정리된 취향', 'preferences': {
                'likes': [{'trait': '조용함', 'importance': 0.6}, {'trait': '체험', 'importance': 0.4}],
                'dislikes': [{'trait': '군중', 'penalty': 0.75}]}},
            'origin': {'category': '공방'}, 'weights': {'taste': 0.7, 'travel': 0.2, 'similarity': 0.1},
            'candidates': [{'id': f'opaque-{i}', 'name': f'시설 {i}', 'description': f'설명 {i}',
                            'category': '공방', 'facts': {'travel_min': {'value': 10 + i}}} for i in range(count)]}


class FakeProvider:
    def __init__(self, value=None, fail_at=None, error_at=None):
        self.value = value or (lambda description, trait: 0.8 if description == '설명 0' else 0.2)
        self.fail_at = fail_at
        self.error_at = error_at
        self.requests = []

    def call(self, lane, request, parser):
        if self.error_at is not None and len(self.requests) == self.error_at:
            class BudgetExceeded(RuntimeError):
                pass
            raise BudgetExceeded('budget_stop')
        self.requests.append(copy.deepcopy(request))
        number = len(self.requests)
        result = {'status': 'failed', 'call_ids': [f'call-{number}'], 'cost_usd': 0.001,
                  'latency_ms': 12.0, 'model': 'jev-test-double',
                  'usage': {'input_tokens': 100, 'output_tokens': 0}}
        answers = {}
        for key, question in request['questions'].items():
            trait = re.search(r'\[(.*?)\]', question['instructions']['question']).group(1)
            answers[key] = {'type': 'noul', 'noul': self.value(question['instructions']['description'], trait)}
        if self.fail_at == number:
            answers[next(iter(answers))]['noul'] = True
        try:
            result.update(parser({'answers': answers}))
            result['status'] = 'ok'
        except (ValueError, KeyError) as error:
            result.update(error_type=type(error).__name__, validation_error=str(error))
        return result


def test_import_does_not_load_sdk_or_credentials():
    code = f"import sys;sys.path.insert(0,{str(HERE)!r});import runner;assert 'openai' not in sys.modules;assert 'dotenv' not in sys.modules;assert 'httpx' not in sys.modules"
    result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_questions_are_atomic_without_context_weights_ids_or_names():
    public = public_fixture()
    saved = copy.deepcopy(public)
    provider = FakeProvider()
    result = rank_features(public, provider)
    assert public == saved
    assert result['status'] == 'ok'
    assert result['question_count'] == 6
    for request in provider.requests:
        assert request['state'] == {}
        assert set(request) == {'model', 'state', 'questions'}
        for q in request['questions'].values():
            assert q['type'] == 'noul'
            assert set(q['instructions']) == {'question', 'description'}
            assert set(q['criteria']) == {'true', 'false'}
            assert q['instructions']['description'] in {'설명 0', '설명 1'}
        encoded = json.dumps(request)
        assert 'importance' not in encoded and 'weights' not in encoded
        assert 'opaque-' not in encoded and 'oracle_' not in encoded


def test_duplicate_trait_is_asked_once_but_each_preference_weight_is_applied():
    public = public_fixture()
    public['customer']['preferences']['likes'].append({'trait': '조용함', 'importance': 0.1})
    questions, _ = build_questions(public)
    assert len(questions) == 6
    decisions = {c['id']: {'조용함': True, '체험': False, '군중': False} for c in public['candidates']}
    _, scores = code_rank(public, decisions)
    assert scores['opaque-0']['taste_positive'] == pytest.approx(0.7)
    assert scores['opaque-0']['taste_grade'] == 0.75


@pytest.mark.parametrize('probability,expected', [(0, False), (0.499999, False), (0.5, True), (0.500001, True), (1, True)])
def test_threshold_is_boolean_not_taste_strength(probability, expected):
    provider = FakeProvider(lambda description, trait: probability)
    result = rank_features(public_fixture(), provider)
    assert result['feature_decisions']['opaque-0']['조용함'] is expected
    assert result['feature_probabilities']['opaque-0']['조용함'] == probability


def test_probabilities_with_same_boolean_decisions_have_same_ranking_and_code_scores():
    public = public_fixture()
    a = rank_features(public, FakeProvider(lambda d, t: 0.51 if t != '군중' else 0.49))
    b = rank_features(public, FakeProvider(lambda d, t: 0.99 if t != '군중' else 0.01))
    assert a['feature_probabilities'] != b['feature_probabilities']
    assert a['feature_decisions'] == b['feature_decisions']
    assert a['code_scores'] == b['code_scores']
    assert a['ranking'] == b['ranking']


@pytest.mark.parametrize('value', [True, False, -0.01, 1.01, float('nan'), float('inf'), '0.5', None])
def test_bad_noul_rejected(value):
    with pytest.raises(ValueError):
        parse_noul({'answers': {'q': {'type': 'noul', 'noul': value}}}, {'q'})


@pytest.mark.parametrize('answers', [{}, {'other': {'type': 'noul', 'noul': 0.5}},
                                    {'q': {'type': 'choice', 'noul': 0.5}}, []])
def test_wrong_answer_set_or_type_rejected(answers):
    with pytest.raises(ValueError):
        parse_noul({'answers': answers}, {'q'})


def test_finite_half_probability_valid():
    assert parse_noul({'answers': {'q': {'type': 'noul', 'noul': 0.5}}}, {'q'}) == {'probabilities': {'q': 0.5}}


@pytest.mark.parametrize('count', [0, 1])
def test_sparse_candidate_uses_code_without_call(count):
    provider = FakeProvider()
    result = rank_features(public_fixture(count), provider)
    assert result['ranking'] == [f'opaque-{i}' for i in range(count)]
    assert result['cost_usd'] == 0 and result['call_ids'] == []
    assert provider.requests == []


def test_batches_at_most_64_and_costs_count_each_call_once():
    provider = FakeProvider()
    result = rank_features(public_fixture(44), provider)
    assert [len(r['questions']) for r in provider.requests] == [64, 64, 4]
    assert result['completed_questions'] == result['question_count'] == 132
    assert result['cost_usd'] == pytest.approx(0.003)
    assert result['latency_ms'] == 36
    assert result['call_ids'] == ['call-1', 'call-2', 'call-3']
    assert all('usage' in part for part in result['subcalls'])
    assert result['model'] == 'jev-test-double'
    assert result['semantic_factuality_verified'] is False
    assert result['evidence_quotes_generated'] is False
    assert 'reasons' not in result


def test_parse_failure_stops_more_chunks_and_keeps_all_paid_costs():
    provider = FakeProvider(fail_at=2)
    result = rank_features(public_fixture(44), provider)
    assert result['status'] == 'failed' and result['ranking'] == []
    assert len(provider.requests) == 2
    assert result['completed_questions'] == 64
    assert result['cost_usd'] == pytest.approx(0.002)
    assert result['call_ids'] == ['call-1', 'call-2']
    assert result['failure']['validation_error'] == 'invalid_noul'


def test_budget_refusal_keeps_prior_cost_and_ids():
    provider = FakeProvider(error_at=1)
    result = rank_features(public_fixture(44), provider)
    assert result['status'] == 'budget_stopped'
    assert result['cost_usd'] == pytest.approx(0.001)
    assert result['call_ids'] == ['call-1']
    assert result['completed_questions'] == 64
    assert result['ranking'] == []


def test_timeout_result_is_failed_and_cost_kept_without_fallback():
    class TimeoutProvider:
        def call(self, lane, request, parser):
            return {'status': 'failed', 'call_ids': ['timed-out'], 'cost_usd': 0.02,
                    'latency_ms': 60000, 'error_type': 'ReadTimeout', 'usage': None}
    result = rank_features(public_fixture(), TimeoutProvider())
    assert result['status'] == 'failed' and result['cost_usd'] == 0.02
    assert result['call_ids'] == ['timed-out']
    assert result['ranking'] == []


def test_dislikes_clip_before_quarter_rounding():
    public = public_fixture()
    decisions = {cid: {'조용함': True, '체험': True, '군중': True} for cid in ('opaque-0', 'opaque-1')}
    _, scores = code_rank(public, decisions)
    assert scores['opaque-0']['taste_positive'] == 1
    assert scores['opaque-0']['taste_penalty'] == 0.75
    assert scores['opaque-0']['taste_grade'] == 0.25
    decisions['opaque-0'] = {'조용함': False, '체험': False, '군중': True}
    _, scores = code_rank(public, decisions)
    assert scores['opaque-0']['taste_clipped'] == 0


@pytest.mark.parametrize('raw,grade', [(0.124, 0), (0.125, 0.25), (0.375, 0.5), (0.625, 0.75), (0.875, 1)])
def test_quarter_rounding_half_goes_up(raw, grade):
    public = public_fixture()
    public['customer']['preferences']['likes'] = [{'trait': '조용함', 'importance': raw}]
    public['customer']['preferences']['dislikes'] = []
    decisions = {c['id']: {'조용함': True} for c in public['candidates']}
    _, scores = code_rank(public, decisions)
    assert scores['opaque-0']['taste_grade'] == grade


def test_weights_and_distance_changes_are_code_only():
    public = public_fixture()
    provider = FakeProvider(lambda d, t: (0.9 if d == '설명 0' and t != '군중' else 0.1))
    first = rank_features(public, provider)
    assert first['ranking'][0] == 'opaque-0'
    changed = copy.deepcopy(public)
    changed['weights'] = {'taste': 0.01, 'travel': 0.99, 'similarity': 0}
    changed['candidates'][0]['facts']['travel_min']['value'] = 60
    second = rank_features(changed, FakeProvider(provider.value))
    assert second['ranking'][0] == 'opaque-1'
    assert first['feature_decisions'] == second['feature_decisions']


def test_candidate_order_and_id_bijection_do_not_change_scores():
    public = public_fixture(4)
    first = rank_features(public, FakeProvider())
    changed = copy.deepcopy(public)
    changed['candidates'].reverse()
    mapping = {c['id']: f'x-{i}' for i, c in enumerate(changed['candidates'])}
    for c in changed['candidates']:
        c['id'] = mapping[c['id']]
    second = rank_features(changed, FakeProvider())
    assert {mapping[k]: v for k, v in first['code_scores'].items()} == second['code_scores']
    assert [mapping[k] for k in first['ranking']] == second['ranking']


@pytest.mark.parametrize('key', ['oracle_taste', 'gold', 'expected', 'labels', 'gold_score_groups'])
def test_hidden_answer_fields_never_enter_questions(key):
    public = public_fixture()
    public['candidates'][0][key] = 1
    provider = FakeProvider()
    with pytest.raises(ValueError, match='oracle_or_gold'):
        rank_features(public, provider)
    assert provider.requests == []


def test_same_stability_cases_as_frozen_selection_with_no_calls():
    cases = [{'case_id': f'case-{i:02d}', 'candidates': list(range(16))} for i in range(12)]
    prepare = lambda c: {'status': 'ready'}
    variant = lambda c, i: (copy.deepcopy(c), 'same_input' if i % 2 == 0 else 'renamed_id_and_permutation', {'x': str(i)})
    work = work_items(cases, 'stability', 20261010, prepare, variant)
    assert len(work) == 16
    assert {c['case_id'] for c, _, _ in work} == {f'case-{i:02d}' for i in range(8)}
    assert sum(condition == 'same_input' for _, condition, _ in work) == 8
    assert len(work_items(cases, 'eval', 20261010, prepare, variant)) == 12
    with pytest.raises(ValueError):
        work_items(cases, 'dev', 20261010, prepare, variant)


def test_actual_48_case_composition_with_perfect_feature_double():
    """The double knows fixture labels; this proves arithmetic, not model quality."""
    frozen = HERE.parent / 'activity_recommendation_retest'
    sys.path.insert(0, str(frozen))
    from fixtures import prepare_case, public_case
    from metrics import evaluate
    data = HERE.parents[2] / 'datasets/travel/activity_recommendation_bench_20261009/retest-20261010/raw/v2/eval.jsonl'
    cases = [json.loads(line) for line in data.read_text(encoding='utf-8').splitlines()]
    assert len(cases) == 48
    for case in cases:
        prepared = prepare_case(case)
        if prepared['status'] != 'ready':
            continue
        mapping = {}
        for c in case['candidates']:
            for trait, provided in c['oracle_traits'].items():
                key = (c['description'], trait)
                assert key not in mapping or mapping[key] == provided
                mapping[key] = provided
        public = public_case(case, prepared['feasible_ids'])
        result = rank_features(public, FakeProvider(lambda description, trait: float(mapping[(description, trait)])))
        measured = evaluate(case, result['ranking'])
        assert result['status'] == 'ok'
        assert measured['format_valid']
        assert measured['top1_correct']
        assert measured['ndcg3'] == pytest.approx(1)
        assert measured['recall3'] == 1
