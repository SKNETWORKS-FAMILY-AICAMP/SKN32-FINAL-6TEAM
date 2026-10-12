# 규정 검색 지표에 신뢰구간과 유의성을 붙인다 — 저장된 측정(results/rag_live_correct*.json)에서 질문별 순위를 읽어 계산하므로 새 호출이 없다.
#  · Recall@k · Hit(상위 k 에 정답) · MRR · nDCG@10: 질문을 복원 추출하는 부트스트랩 95% 구간(B=10,000). 비율은 Wilson 구간도 같이.
#  · 개선 전(운영 색인 A) 대 후(색인 E): 같은 질문에서 짝지은 부트스트랩 평균 차이 구간 + McNemar 정확검정(Recall@3 의 정오).
#  · 답 없는 질문(uncovered · offtopic)에 규정을 보인 비율(새어 나감)과 근접 질문 보임 비율: Wilson 구간.
# 사용: python rag_ci_report.py  → results/rag_ci_report.txt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', 'eval_kit')))
sys.stdout.reconfigure(encoding='utf-8')
from stats import bootstrap_ci, fmt_ratio, mcnemar_exact, paired_bootstrap_diff, wilson  # noqa: E402

J = lambda *a: json.load(open(os.path.join(HERE, *a), encoding='utf-8'))
BEF, AFT = J('results', 'rag_live_correct.json'), J('results', 'rag_live_correct_E.json')
TAU = 0.55


def per_question(rows, k=3):
    """답 있음 질문마다 (Hit@k, RR, nDCG@10, 상위1 정답) — 정답 줄 gold 기준."""
    out = []
    for r in rows:
        if r['type'] != 'answerable':
            continue
        gold = set(r['gold'])
        order = [s for s, _ in r['rank']]
        hit = bool(set(order[:k]) & gold)
        pos = next((i for i, s in enumerate(order) if s in gold), None)
        rr = 1 / (pos + 1) if pos is not None else 0.0
        dcg = sum(1 / math.log2(i + 2) for i, s in enumerate(order[:10]) if s in gold)
        idcg = sum(1 / math.log2(i + 2) for i in range(min(len(gold), 10)))
        top3 = order[:3]
        out.append({'hit1': order[0] in gold, 'hit2': bool(set(order[:2]) & gold), 'hit3': bool(set(order[:3]) & gold), 'hit5': bool(set(order[:5]) & gold), 'rr': rr, 'ndcg': dcg / idcg,
                    'cap_recall3': len(set(top3) & gold) / min(3, len(gold)), 'p3': len(set(top3) & gold) / 3, 'rprec': len(set(order[:len(gold)]) & gold) / len(gold)})
    return out


def line(name, vals, kind):
    n = len(vals)
    if kind == 'ratio':
        k = sum(1 for v in vals if v)
        return f'{name}: {fmt_ratio(k, n)}'
    point, lo, hi = bootstrap_ci(vals, lambda u: sum(u) / len(u), B=10000)
    return f'{name}: {point:.3f} (부트스트랩 95% 구간 {lo:.3f}~{hi:.3f}, n={n})'


print('# 규정 검색 지표 — 신뢰구간 · 유의성 (질문은 모두 모델이 쓴 합성, 1회 측정)')
print('- 구간: 비율은 Wilson 95%, 평균(MRR · nDCG)은 질문 복원 추출 부트스트랩 95%(B=10,000). 작은 표본이라 구간이 넓다 — 점추정만 읽지 않는다.\n')
for sname in ('A', 'B'):
    b, a = per_question(BEF['correct'][sname]), per_question(AFT['correct'][sname])
    print(f'## 세트 {sname} — 답 있음 {len(b)}문제')
    for lab, rows in (('개선 전(운영 색인)', b), ('개선 후(색인 E)', a)):
        print(f'- {lab}')
        for key, nm in (('hit1', 'Hit@1'), ('hit2', 'Hit@2(고객에게 보이는 줄 수)'), ('hit3', 'Hit@3(= 정답이 상위 3 안에 하나라도)'), ('hit5', 'Hit@5')):
            print('   ' + line(nm, [r[key] for r in rows], 'ratio'))
        for key, nm in (('cap_recall3', 'Recall@3(정답 수와 3 중 작은 쪽으로 나눔, BEIR)'), ('p3', 'Precision@3'), ('rprec', 'R-precision')):
            print('   ' + line(nm, [r[key] for r in rows], 'mean'))
        print('   ' + line('MRR', [r['rr'] for r in rows], 'mean'))
        print('   ' + line('nDCG@10', [r['ndcg'] for r in rows], 'mean'))
    d = paired_bootstrap_diff([r['hit3'] for r in a], [r['hit3'] for r in b])
    mc = mcnemar_exact([r['hit3'] for r in a], [r['hit3'] for r in b])
    d_mrr = paired_bootstrap_diff([r['rr'] for r in a], [r['rr'] for r in b])
    print(f"- 개선 후 − 개선 전 Recall@3 차이: {d['diff']:+.3f} (짝지은 부트스트랩 95% 구간 {d['lo']:+.3f}~{d['hi']:+.3f}) · McNemar 정확검정 개선 후만 맞음 {mc['a_only']} · 개선 전만 맞음 {mc['b_only']} · p={mc['p']:.3g}")
    print(f"- MRR 차이: {d_mrr['diff']:+.3f} (95% 구간 {d_mrr['lo']:+.3f}~{d_mrr['hi']:+.3f})")
    for lab, doc in (('개선 전', BEF), ('개선 후', AFT)):
        rows = doc['correct'][sname]
        neg = [r for r in rows if r['type'] in ('uncovered', 'offtopic')]
        leak = sum(1 for r in neg if r['sources'])
        nm = [r for r in rows if r['type'] == 'near_miss']
        nms = sum(1 for r in nm if r['sources'])
        print(f'- {lab} · 답 없는 질문에 규정을 보임(새어 나감): {fmt_ratio(leak, len(neg))} · 근접·부분 답 질문에 보임: {fmt_ratio(nms, len(nm))}')
    print()
print('## 읽는 법')
print('- 구간이 겹치지 않으면(또는 짝지은 차이 구간이 0 을 포함하지 않으면) 차이가 우연이 아닐 가능성이 크다. 겹치면 「구분되지 않는다」.')
print('- 이 값은 합성 질문 기준이다. 정답 라벨은 질문 작성자(A) 또는 다른 모델 호출(B)이 달았고 사람이 검수하지 않았다.')
