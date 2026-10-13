# §60-2 R4 — Decider-12B 8비트에서 일정 목록을 0·10·21·32칸 돌려 푼 확률 4개의 평균 대 원래 순서 8비트. 4세트 합산 + 가능한 세트 모두, 짝지은 정확 McNemar(p<0.05 가 「줄인다」).
# 사용: python eval_r4.py [세트들,쉼표]   (기본 mix8,mix9,mix10,mix11,mix12 중 회전 파일이 모두 있는 세트만)
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda n: os.path.join(HERE, 'results', n)
SETS = sys.argv[1].split(',') if len(sys.argv) > 1 else ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
TAGS = ['decider12bq8', 'decider12bq8rot10', 'decider12bq8rot21', 'decider12bq8rot32']


def pick(k):
    return int(k.split('_')[1]) if k.startswith('item_') else None


def norm(p):
    s = sum(p.values())
    return {k: v / s for k, v in p.items()}


def mcnemar(a, b):
    n10 = sum(1 for x, y in zip(a, b) if x and not y)
    n01 = sum(1 for x, y in zip(a, b) if y and not x)
    n = n10 + n01
    if n == 0:
        return n10, n01, 1.0
    k = min(n10, n01)
    return n10, n01, min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n)


use = [w for w in SETS if all(os.path.exists(R(f'dec_{t}_{w}.json')) for t in TAGS)]
print('사용 세트:', use, '· 빠진 세트:', [w for w in SETS if w not in use])
tot = {t: 0 for t in TAGS}
base_v, avg_v, avg3_v, n_all = [], [], [], 0
for w in use:
    gold = [x['gold'] for x in json.load(open(os.path.join(HERE, 'fixtures', f'{w}.json'), encoding='utf-8'))['sets'][w]['qs']]
    P = {t: [norm(r['probs']) for r in json.load(open(R(f'dec_{t}_{w}.json'), encoding='utf-8'))[w]['rows']] for t in TAGS}
    per = {}
    for t in TAGS:
        v = [int(pick(max(p, key=p.get)) == g) if p else 0 for p, g in zip(P[t], gold)]
        per[t] = sum(v)
        tot[t] += sum(v)
    base_v += [int(pick(max(p, key=p.get)) == g) for p, g in zip(P[TAGS[0]], gold)]
    for use_tags, vec in ((TAGS, avg_v), (TAGS[:3], avg3_v)):
        for i, g in enumerate(gold):
            t = {}
            for tag in use_tags:
                for k, x in P[tag][i].items():
                    t[k] = t.get(k, 0.0) + x
            vec.append(int(pick(max(t, key=t.get)) == g))
    n_all += len(gold)
    a4 = sum(avg_v[-len(gold):])
    print(f'{w}: 원래 {per[TAGS[0]]} · 회전10 {per[TAGS[1]]} · 회전21 {per[TAGS[2]]} · 회전32 {per[TAGS[3]]} · 4개 평균 {a4}/{len(gold)}')
print(f'합계 {n_all}문제: 원래 {tot[TAGS[0]]} · 회전10 {tot[TAGS[1]]} · 회전21 {tot[TAGS[2]]} · 회전32 {tot[TAGS[3]]} · 4개 평균(R4) {sum(avg_v)} · 3개 평균(0·10·21) {sum(avg3_v)}')
for nm, v in (('R4(4개 평균)', avg_v), ('3개 평균', avg3_v)):
    n10, n01, p = mcnemar(v, base_v)
    verdict = '줄인다(점추정 앞섬, p<0.05)' if sum(v) > sum(base_v) and p < 0.05 else '구분되지 않는다'
    print(f'{nm} 대 원래 순서 8비트: {sum(v) - sum(base_v):+d}문제 (평균만 맞음 {n10} · 원래만 맞음 {n01}, 정확 McNemar p={p:.3f}) → {verdict}')
