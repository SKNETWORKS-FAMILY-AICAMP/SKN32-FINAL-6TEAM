"""평가 통계 공용 도구 — 측정값마다 신뢰구간·유의성·일치도를 같은 방식으로 내기 위한 모음 (2026-10-06).

각 함수의 정의와 근거(문헌)는 함수 설명에 적었다. 시험은 test_stats.py (알려진 값과 대조).
의존: numpy, scipy.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Callable, Sequence

import numpy as np
from scipy import stats as _st


# ---------------------------------------------------------------- 비율의 신뢰구간
def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Wilson 점수 구간 — 작은 표본·0 또는 100% 근처에서 Wald 구간보다 안정적(Brown·Cai·DasGupta 2001)."""
    if n == 0:
        return (0.0, 1.0)
    z = _st.norm.ppf(1 - (1 - conf) / 2)
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, center - half), min(1.0, center + half))


def clopper_pearson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Clopper–Pearson 정확 구간(보수적). 베타 분포 분위수."""
    if n == 0:
        return (0.0, 1.0)
    a = (1 - conf) / 2
    lo = 0.0 if k == 0 else _st.beta.ppf(a, k, n - k + 1)
    hi = 1.0 if k == n else _st.beta.ppf(1 - a, k + 1, n - k)
    return (float(lo), float(hi))


def fmt_ratio(k: int, n: int, conf: float = 0.95) -> str:
    """「k/n = p% (95% 구간 lo~hi%)」 — 문서에 그대로 쓰는 모양(Wilson)."""
    if n == 0:
        return '0/0'
    lo, hi = wilson(k, n, conf)
    return f'{k}/{n} = {100 * k / n:.1f}% (95% 구간 {100 * lo:.1f}~{100 * hi:.1f}%)'


# ---------------------------------------------------------------- 부트스트랩
def bootstrap_ci(units: Sequence, stat: Callable[[Sequence], float], B: int = 10000, conf: float = 0.95, seed: int = 20261006) -> tuple[float, float, float]:
    """질문(단위)을 복원 추출해 통계량의 백분위 구간을 낸다(Efron). 반환: (점추정, 하한, 상한). 단위가 상관돼 있으면(같은 일정 등) 단위를 묶어서 넘길 것."""
    rng = np.random.default_rng(seed)
    n = len(units)
    arr = list(units)
    point = float(stat(arr))
    vals = np.empty(B)
    for b in range(B):
        idx = rng.integers(0, n, n)
        vals[b] = stat([arr[i] for i in idx])
    a = (1 - conf) / 2
    return point, float(np.quantile(vals, a)), float(np.quantile(vals, 1 - a))


def paired_bootstrap_diff(a: Sequence[float], b: Sequence[float], B: int = 10000, conf: float = 0.95, seed: int = 20261006) -> dict:
    """같은 질문에서 A·B 점수(0/1 또는 실수)를 짝지어 평균 차이의 구간과 한쪽 우세 확률을 낸다(IR 평가의 짝지은 부트스트랩, Sakai 2006·Smucker 2007)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a - b
    rng = np.random.default_rng(seed)
    n = len(d)
    boots = np.array([d[rng.integers(0, n, n)].mean() for _ in range(B)])
    al = (1 - conf) / 2
    return {'diff': float(d.mean()), 'lo': float(np.quantile(boots, al)), 'hi': float(np.quantile(boots, 1 - al)),
            'p_a_not_better': float((boots <= 0).mean()), 'n': n}


def mcnemar_exact(a_ok: Sequence[bool], b_ok: Sequence[bool]) -> dict:
    """짝지은 정오(0/1)의 McNemar 정확검정(Dietterich 1998 권고 — 분류기 비교). 불일치 쌍만 쓴다. 양측 p."""
    x = sum(1 for p, q in zip(a_ok, b_ok) if p and not q)
    y = sum(1 for p, q in zip(a_ok, b_ok) if q and not p)
    n = x + y
    p = 1.0 if n == 0 else min(1.0, 2 * float(_st.binom.cdf(min(x, y), n, 0.5)))
    return {'a_only': x, 'b_only': y, 'p': p}


# ---------------------------------------------------------------- 일치도
def cohen_kappa(r1: Sequence, r2: Sequence, weights: str | None = None, labels: Sequence | None = None) -> float:
    """Cohen 카파(두 평가자). weights=None 이면 일치/불일치, 'linear'·'quadratic' 이면 순서 라벨용 가중 카파(Cohen 1968)."""
    labs = list(labels) if labels is not None else sorted(set(r1) | set(r2), key=lambda x: (str(type(x)), x))
    k = len(labs)
    idx = {l: i for i, l in enumerate(labs)}
    n = len(r1)
    O = np.zeros((k, k))
    for p, q in zip(r1, r2):
        O[idx[p], idx[q]] += 1
    O /= n
    E = np.outer(O.sum(1), O.sum(0))
    W = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            if weights is None:
                W[i, j] = 0.0 if i == j else 1.0
            elif weights == 'linear':
                W[i, j] = abs(i - j) / (k - 1) if k > 1 else 0.0
            else:
                W[i, j] = ((i - j) / (k - 1)) ** 2 if k > 1 else 0.0
    den = (W * E).sum()
    return 1.0 if den == 0 else 1.0 - (W * O).sum() / den


def gwet_ac1(r1: Sequence, r2: Sequence) -> float:
    """Gwet AC1(두 평가자, 명목) — 한 라벨에 몰릴 때(유병률 높음) 카파가 낮게 나오는 문제를 줄인다(Gwet 2008)."""
    labs = sorted(set(r1) | set(r2), key=lambda x: (str(type(x)), x))
    n = len(r1)
    po = sum(1 for p, q in zip(r1, r2) if p == q) / n
    pi = {l: (sum(1 for x in r1 if x == l) + sum(1 for x in r2 if x == l)) / (2 * n) for l in labs}
    pe = sum(v * (1 - v) for v in pi.values()) / (len(labs) - 1) if len(labs) > 1 else 0.0
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def krippendorff_alpha(data: Sequence[Sequence], level: str = 'nominal') -> float:
    """Krippendorff 알파 — 평가자 수·결측에 상관없이 쓴다(Krippendorff 2011). data[평가자][항목] (결측은 None). level: nominal | ordinal | interval."""
    m = len(data)
    n_items = len(data[0])
    units = []
    for u in range(n_items):
        vals = [data[r][u] for r in range(m) if data[r][u] is not None]
        if len(vals) >= 2:
            units.append(vals)
    cats = sorted({v for u in units for v in u}, key=lambda x: (str(type(x)), x))
    ci = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    o = np.zeros((k, k))
    for vals in units:
        mu = len(vals)
        cnt = Counter(vals)
        for c in cnt:
            for d in cnt:
                pairs = cnt[c] * (cnt[d] - (1 if c == d else 0))
                o[ci[c], ci[d]] += pairs / (mu - 1)
    nc = o.sum(1)
    ntot = nc.sum()
    if ntot <= 1:
        return float('nan')

    def delta2(i: int, j: int) -> float:
        if i == j:
            return 0.0
        if level == 'nominal':
            return 1.0
        if level == 'interval':
            return float((cats[i] - cats[j]) ** 2)
        lo, hi = min(i, j), max(i, j)       # ordinal: 누적 빈도 사용
        return float((nc[lo:hi + 1].sum() - (nc[lo] + nc[hi]) / 2) ** 2)

    do = sum(o[i, j] * delta2(i, j) for i in range(k) for j in range(k))
    de = sum(nc[i] * nc[j] * delta2(i, j) for i in range(k) for j in range(k)) / (ntot - 1)
    return 1.0 if de == 0 else 1.0 - do / de


# ---------------------------------------------------------------- 분류 지표
def prf_table(gold: Sequence, pred: Sequence, labels: Sequence) -> dict:
    """클래스별 정밀도·재현율·F1·지원수 + micro/macro/weighted F1 + 정확도. 지원수 0 인 클래스는 macro 에서 뺀다(그 클래스 값은 None)."""
    per = {}
    for lab in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == lab and p == lab)
        fp = sum(1 for g, p in zip(gold, pred) if g != lab and p == lab)
        fn = sum(1 for g, p in zip(gold, pred) if g == lab and p != lab)
        sup = tp + fn
        P = tp / (tp + fp) if tp + fp else None
        R = tp / sup if sup else None
        F = (2 * P * R / (P + R)) if (P and R) else (0.0 if sup else None)
        per[lab] = {'p': P, 'r': R, 'f1': F, 'support': sup, 'tp': tp, 'fp': fp, 'fn': fn}
    n = len(gold)
    acc = sum(1 for g, p in zip(gold, pred) if g == p) / n if n else 0.0
    fs = [v['f1'] for v in per.values() if v['support'] and v['f1'] is not None]
    tot_tp = sum(v['tp'] for v in per.values())
    tot_fp = sum(v['fp'] for v in per.values())
    tot_fn = sum(v['fn'] for v in per.values())
    micro_p = tot_tp / (tot_tp + tot_fp) if tot_tp + tot_fp else 0.0
    micro_r = tot_tp / (tot_tp + tot_fn) if tot_tp + tot_fn else 0.0
    micro = 2 * micro_p * micro_r / (micro_p + micro_r) if micro_p + micro_r else 0.0
    wsum = sum(v['support'] for v in per.values() if v['f1'] is not None)
    weighted = sum(v['support'] * v['f1'] for v in per.values() if v['f1'] is not None) / wsum if wsum else 0.0
    return {'per_class': per, 'accuracy': acc, 'macro_f1': (sum(fs) / len(fs) if fs else 0.0), 'micro_f1': micro, 'weighted_f1': weighted, 'n': n}


def mcc_multiclass(gold: Sequence, pred: Sequence, labels: Sequence) -> float:
    """다중 클래스 Matthews 상관계수(Gorodkin 2004) — 불균형에서도 한 숫자로 보는 용도."""
    idx = {l: i for i, l in enumerate(labels)}
    k = len(labels)
    C = np.zeros((k, k))
    for g, p in zip(gold, pred):
        if g in idx and p in idx:
            C[idx[g], idx[p]] += 1
    t = C.sum(1)
    pk = C.sum(0)
    c = np.trace(C)
    s = C.sum()
    num = c * s - float((t * pk).sum())
    den = math.sqrt(max(s * s - float((pk * pk).sum()), 0.0) * max(s * s - float((t * t).sum()), 0.0))
    return 0.0 if den == 0 else num / den


def ece(confidences: Sequence[float], correct: Sequence[bool], bins: int = 15) -> dict:
    """기대 보정 오차 ECE(Guo 등 2017, 같은 폭 15칸) + Brier(이진 정오). 확신도 = 예측 클래스의 확률."""
    c = np.asarray(confidences, float)
    y = np.asarray(correct, float)
    edges = np.linspace(0, 1, bins + 1)
    e = 0.0
    rows = []
    for i in range(bins):
        m = (c > edges[i]) & (c <= edges[i + 1]) if i else (c >= edges[i]) & (c <= edges[i + 1])
        if m.sum():
            gap = abs(y[m].mean() - c[m].mean())
            e += m.mean() * gap
            rows.append((float(edges[i]), float(edges[i + 1]), int(m.sum()), float(c[m].mean()), float(y[m].mean())))
    return {'ece': float(e), 'brier': float(((c - y) ** 2).mean()), 'bins': rows}


# ---------------------------------------------------------------- 지연시간·신뢰성
def percentile(values: Sequence[float], q: float, method: str = 'linear') -> float:
    """백분위(q = 0~100). method: 'linear'(numpy 기본, 보간) · 'nearest'(최근접 순위 — 작은 표본에서 p99 가 최댓값이 됨을 드러낸다). 보고할 때 방법과 표본 수를 함께 적는다."""
    v = np.sort(np.asarray(values, float))
    if len(v) == 0:
        return float('nan')
    if method == 'nearest':
        k = max(1, math.ceil(q / 100 * len(v)))
        return float(v[k - 1])
    return float(np.percentile(v, q))


def latency_summary(values_ms: Sequence[float]) -> dict:
    """p50·p90·p95·p99·최댓값·평균과 표본 수. p99 는 표본 100개 미만이면 사실상 최댓값 — n 을 같이 보고해야 한다."""
    v = list(values_ms)
    return {'n': len(v), 'p50': percentile(v, 50), 'p90': percentile(v, 90), 'p95': percentile(v, 95), 'p99': percentile(v, 99), 'max': max(v) if v else float('nan'), 'mean': float(np.mean(v)) if v else float('nan')}


def pass_hat_k(successes_per_task: Sequence[int], trials_per_task: int, k: int) -> float:
    """pass^k(τ-bench, Yao 등 2024): 과제마다 n 번 시도해 c 번 성공했을 때 k 번 모두 성공할 확률의 비편향 추정 E[C(c,k)/C(n,k)]."""
    n = trials_per_task
    if k > n:
        raise ValueError('k 는 시도 횟수 이하여야 한다')
    return float(np.mean([math.comb(c, k) / math.comb(n, k) for c in successes_per_task]))
