# rag_metrics_report.py 와 같은 계산 함수(검색 지표·운영 규칙 재현·문턱 판정)를 모은 것 — 개선 전후 비교 스크립트가 쓴다.
import math
import os
HERE = os.path.dirname(os.path.abspath(__file__))
import json
J = lambda *a: json.load(open(os.path.join(HERE, *a), encoding='utf-8'))
CH = J('fixtures', 'policy_chunks.json')
LINE = {c['source']: c['line'] for c in CH if c['line']}
TAUS = [round(0.30 + 0.025 * k, 3) for k in range(0, 21)]
KEYT = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]


def rel(row):
    """정답 줄 — 답 있음 유형만(A: gold · B: gold=full). 그 밖 유형은 비어 있다."""
    return set(row['gold']) if row['type'] == 'answerable' else set()


def retrieval(rows, ks=(1, 3, 5, 10), rel_of=rel):
    qs = [r for r in rows if rel_of(r) and r.get('rank')]
    out = {'n': len(qs)}
    for k in ks:
        P, R, F = [], [], []
        for r in qs:
            top = [s for s, _ in r['rank'][:k]]
            h = len(set(top) & rel_of(r))
            p, rc = h / k, h / len(rel_of(r))
            P.append(p), R.append(rc), F.append(0 if p + rc == 0 else 2 * p * rc / (p + rc))
        out[k] = (sum(P) / len(P), sum(R) / len(R), sum(F) / len(F), sum(1 for r in qs if set(s for s, _ in r['rank'][:k]) & rel_of(r)))
    mrr = []
    ndcg = []
    for r in qs:
        order = [s for s, _ in r['rank']]
        rr = next((1 / (i + 1) for i, s in enumerate(order) if s in rel_of(r)), 0.0)
        mrr.append(rr)
        dcg = sum(1 / math.log2(i + 2) for i, s in enumerate(order[:10]) if s in rel_of(r))
        idcg = sum(1 / math.log2(i + 2) for i in range(min(len(rel_of(r)), 10)))
        ndcg.append(dcg / idcg)
    out['mrr'] = sum(mrr) / len(mrr)
    out['ndcg10'] = sum(ndcg) / len(ndcg)
    return out


def shown(row, tau, top3=3, top=2):
    """운영 규칙 재현: 순위 상위 3개 중 점수 ≥ τ, 고객용 문장이 있는 절을 점수 순으로 모아 같은 문장은 한 번만, 최대 2개."""
    out, seen = [], []
    for s, sc in row['rank'][:top3]:
        if sc >= tau and s in LINE and LINE[s] not in seen:
            seen.append(LINE[s])
            out.append(s)
        if len(out) >= top:
            break
    return out


def confusion(rows, tau, neg_types=('uncovered', 'offtopic')):
    tp = fn = fp = tn = 0
    for r in rows:
        if not r.get('rank'):
            continue
        sh = bool(shown(r, tau))
        if r['type'] == 'answerable':
            tp += sh
            fn += (not sh)
        elif r['type'] in neg_types:
            fp += sh
            tn += (not sh)
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return {'tp': tp, 'fn': fn, 'fp': fp, 'tn': tn, 'p': pr, 'r': rc, 'f1': 0 if pr + rc == 0 else 2 * pr * rc / (pr + rc)}


def best_tau(rows, neg_types):
    best = max(TAUS, key=lambda t: (round(confusion(rows, t, neg_types)['f1'], 6), t))
    return best


def pct(a, b):
    return f'{a}/{b}={100 * a / b:.1f}%' if b else '0/0'


