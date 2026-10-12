"""stats.py 시험 — 알려진 값(교과서·참고 구현)과 대조한다. 실행: python -m pytest program/scripts/eval_kit/test_stats.py -q"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stats as S  # noqa: E402


def test_wilson_matches_scipy_reference():
    from scipy.stats import binomtest
    for k, n in [(81, 100), (0, 10), (10, 10), (3, 35), (700, 769)]:
        ref = binomtest(k, n).proportion_ci(confidence_level=0.95, method='wilson')
        lo, hi = S.wilson(k, n)
        assert lo == pytest.approx(ref.low, abs=1e-9) and hi == pytest.approx(ref.high, abs=1e-9)


def test_clopper_pearson_known_values():
    lo, hi = S.clopper_pearson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.3085, abs=2e-3)   # 1-0.025**(1/10)
    lo, hi = S.clopper_pearson(5, 10)
    assert lo == pytest.approx(0.1871, abs=2e-3) and hi == pytest.approx(0.8129, abs=2e-3)


def test_mcnemar_matches_binomial():
    a = [True] * 13 + [False] * 3 + [True] * 50
    b = [False] * 13 + [True] * 3 + [True] * 50
    r = S.mcnemar_exact(a, b)
    assert (r['a_only'], r['b_only']) == (13, 3)
    assert r['p'] == pytest.approx(0.02127, abs=1e-4)           # 13:3 → p=0.0213 (마스터 문서 §92-9 와 같은 값)


def test_cohen_kappa_textbook():
    # 교과서 예(Cohen 1960 식): 50 항목, 20 예-예, 15 아니오-아니오, 5, 10 → po=0.7, pe=0.5 → κ=0.4
    r1 = ['y'] * 25 + ['n'] * 25
    r2 = ['y'] * 20 + ['n'] * 5 + ['y'] * 10 + ['n'] * 15
    assert S.cohen_kappa(r1, r2) == pytest.approx(0.4, abs=1e-9)


def test_weighted_kappa_perfect_and_quadratic():
    r = [1, 2, 3, 4, 5, 3, 2]
    assert S.cohen_kappa(r, r, weights='quadratic') == pytest.approx(1.0)
    assert S.cohen_kappa([1, 2, 3, 3], [1, 2, 3, 3], weights='linear') == pytest.approx(1.0)


def test_krippendorff_wikipedia_example():
    # Wikipedia 「Krippendorff's alpha」 예: 평가자 3명 · 15항목 · 결측 있음 → 명목 α = 0.691
    A = [None, None, None, None, None, 3, 4, 1, 2, 1, 1, 3, 3, None, 3]
    B = [1, None, 2, 1, 3, 3, 4, 3, None, None, None, None, None, None, None]
    C = [None, None, 2, 1, 3, 4, 4, None, 2, 1, 1, 3, 3, None, 4]
    assert S.krippendorff_alpha([A, B, C], 'nominal') == pytest.approx(0.691, abs=1e-3)
    assert S.krippendorff_alpha([['a', 'b', 'a', 'c'], ['a', 'b', 'a', 'c']]) == pytest.approx(1.0)


def test_gwet_ac1_high_prevalence():
    r1 = ['y'] * 90 + ['n'] * 10
    r2 = ['y'] * 85 + ['n'] * 5 + ['y'] * 5 + ['n'] * 5
    k = S.cohen_kappa(r1, r2)
    ac1 = S.gwet_ac1(r1, r2)
    assert ac1 > k                        # 유병률이 높을 때 카파는 낮게, AC1 은 높게


def test_prf_matches_sklearn():
    from sklearn.metrics import f1_score, precision_recall_fscore_support
    gold = ['a', 'a', 'b', 'b', 'b', 'c', 'c', 'a', 'b', 'c']
    pred = ['a', 'b', 'b', 'b', 'c', 'c', 'c', 'a', 'a', 'b']
    t = S.prf_table(gold, pred, ['a', 'b', 'c'])
    assert t['macro_f1'] == pytest.approx(f1_score(gold, pred, average='macro'))
    assert t['micro_f1'] == pytest.approx(f1_score(gold, pred, average='micro'))
    assert t['weighted_f1'] == pytest.approx(f1_score(gold, pred, average='weighted'))
    p, r, f, _ = precision_recall_fscore_support(gold, pred, labels=['a', 'b', 'c'])
    for i, lab in enumerate(['a', 'b', 'c']):
        assert t['per_class'][lab]['f1'] == pytest.approx(f[i])


def test_mcc_matches_sklearn():
    from sklearn.metrics import matthews_corrcoef
    gold = ['a', 'a', 'b', 'b', 'b', 'c', 'c', 'a', 'b', 'c']
    pred = ['a', 'b', 'b', 'b', 'c', 'c', 'c', 'a', 'a', 'b']
    assert S.mcc_multiclass(gold, pred, ['a', 'b', 'c']) == pytest.approx(matthews_corrcoef(gold, pred))


def test_ece_perfectly_calibrated_and_overconfident():
    rng = np.random.default_rng(0)
    c = rng.uniform(0.5, 1.0, 20000)
    y = rng.uniform(0, 1, 20000) < c
    assert S.ece(c, y)['ece'] < 0.02
    assert S.ece([0.99] * 100, [True] * 50 + [False] * 50)['ece'] == pytest.approx(0.49, abs=1e-6)


def test_percentile_methods():
    v = list(range(1, 101))
    assert S.percentile(v, 95, 'nearest') == 95
    assert S.percentile(v, 99, 'nearest') == 99
    assert S.percentile([1, 2, 3, 4, 5], 99, 'nearest') == 5       # 표본이 작으면 p99 = 최댓값
    assert S.percentile(v, 50) == pytest.approx(50.5)


def test_pass_hat_k_tau_bench_formula():
    # 과제 3개, 각 4번 시도, 성공 4·2·0 번. pass^1 = (1 + 0.5 + 0)/3, pass^2 = (1 + 1/6 + 0)/3, pass^4 = (1+0+0)/3
    assert S.pass_hat_k([4, 2, 0], 4, 1) == pytest.approx(0.5)
    assert S.pass_hat_k([4, 2, 0], 4, 2) == pytest.approx((1 + 1 / 6) / 3)
    assert S.pass_hat_k([4, 2, 0], 4, 4) == pytest.approx(1 / 3)


def test_bootstrap_ci_contains_truth():
    units = [1] * 80 + [0] * 20
    point, lo, hi = S.bootstrap_ci(units, lambda u: sum(u) / len(u), B=2000)
    assert point == pytest.approx(0.8) and lo < 0.8 < hi
    assert lo == pytest.approx(0.72, abs=0.04) and hi == pytest.approx(0.88, abs=0.04)


def test_paired_bootstrap_detects_difference():
    a = [1] * 90 + [0] * 10
    b = [1] * 60 + [0] * 40
    r = S.paired_bootstrap_diff(a, b, B=2000)
    assert r['diff'] == pytest.approx(0.3) and r['lo'] > 0 and r['p_a_not_better'] < 0.01
