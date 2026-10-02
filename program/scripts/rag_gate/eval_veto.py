# 거부권(veto) 채점 — 운영식(임베딩 상위 3 · 점수 ≥ τ · 고객용 문장 2개)이 만든 후보 위에 판정 모델이 「최고 판정 확률 < τv 면 못 찾음」 거부권만 얹는다. 판정은 같은 질문의 상위 5개 후보 줄에 대한 p_true.
#  사용: python eval_veto.py <판정 모델 파일 이름 접미(예: gemma4_12b__E)> [VARIANT 이름(임베딩 변형, 생략하면 rag_sims.json)]
#  τv 와 가지치기는 짝수 번째(개발용)로 고르고 홀수 번째(시험용)로 판정. 점수 = 정답 줄 보임 +1 · 틀린 줄만 −2 · 답 없는데 답함 −2(부분 답/비슷하지만 다름은 따로 셈).
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda *a: json.load(open(os.path.join(HERE, *a), encoding='utf-8'))
Q = J('fixtures', 'rag_questions.json')['questions']
CH = J('fixtures', 'policy_chunks.json')
LINE = {c['source'] for c in CH if c['line']}
suffix = sys.argv[1]
var = sys.argv[2] if len(sys.argv) > 2 else None
if var:
    v = J('results', 'rag_embed_variants.json')
    SRC, SIM = v['sources'], v['variants'][var]
else:
    s = J('results', 'rag_sims.json')
    SRC, SIM = s['sources'], s['sims']
JD = J('results', f'rag_judge_{suffix}.json')
N = len(Q)
DEV = [i for i in range(N) if i % 2 == 0]
TEST = [i for i in range(N) if i % 2 == 1]


def prod(qi, tau=0.55, topk=3, top=2):
    order = sorted(range(len(SRC)), key=lambda i: -SIM[qi][i])[:topk]
    return [SRC[i] for i in order if SIM[qi][i] >= tau and SRC[i] in LINE][:top]


def pm(qi):
    return {s: p for s, v, p in JD['judge'][str(qi)] if p is not None}


def maxp(qi):
    d = pm(qi)
    return max(d.values()) if d else 0.0


def outcome(qi, sh):
    q = Q[qi]
    if q['type'] == 'answerable':
        if not sh:
            return 'miss', 0
        return ('correct', 1) if set(sh) & set(q['gold']) else ('wrong', -2)
    return ('abstain', 0) if not sh else ('false', -2)


def tally(idx, fn):
    c = {'correct': 0, 'miss': 0, 'wrong': 0, 'false': 0, 'near': 0, 'near_n': 0, 'score': 0}
    for qi in idx:
        o, s = outcome(qi, fn(qi))
        if Q[qi]['type'] == 'near_miss':
            c['near_n'] += 1
            c['near'] += o == 'false'
            continue
        if o in c:
            c[o] += 1
        c['score'] += s
    return c


def veto(tv, prune=None, tau=0.55):
    def f(qi):
        sh = prod(qi, tau)
        if not sh or maxp(qi) < tv:
            return []
        if prune is not None:
            d = pm(qi)
            sh = [x for x in sh if d.get(x, 1.0) >= prune]
        return sh
    return f


n_ans = sum(q['type'] == 'answerable' for q in Q)
n_none = sum(q['type'] in ('uncovered', 'offtopic') for q in Q)
n_near = sum(q['type'] == 'near_miss' for q in Q)
print(f'## 판정 거부권 — 판정 {suffix}, 후보 {"변형 " + var if var else "운영 본문 색인"}, {N}문제(답 있음 {n_ans} · 답 없음 {n_none} · 부분 답/비슷함 {n_near})')
print('| 방식 | 정답 줄 보임 | 틀린 줄만 | 못 찾음 | 답 없음에 답함 | 부분 답/비슷함에 답함 | 점수 |')
print('|---|---:|---:|---:|---:|---:|---:|')


def row(name, c):
    print(f"| {name} | {c['correct']}/{n_ans} | {c['wrong']} | {c['miss']} | {c['false']}/{n_none} | {c['near']}/{n_near} | **{c['score']}** |")


row('후보 그대로(τ 0.55)', tally(range(N), lambda qi: prod(qi)))
for tv in (0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
    row(f'거부권 p<{tv}', tally(range(N), veto(tv)))
for tv, pr in ((0.1, 0.1), (0.2, 0.2), (0.5, 0.5)):
    row(f'거부권 p<{tv} + 줄 가지치기 p<{pr}', tally(range(N), veto(tv, pr)))
cfgs = [(tv, pr) for tv in (0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9) for pr in (None, 0.05, 0.1, 0.2, 0.5)]
best = max(cfgs, key=lambda c: tally(DEV, veto(*c))['score'])
d = [outcome(qi, veto(*best)(qi))[1] - outcome(qi, prod(qi))[1] for qi in TEST if Q[qi]['type'] != 'near_miss']
r = random.Random(20261001)
bs = sorted(sum(r.choice(d) for _ in d) / len(d) for _ in range(2000))
print(f'\n개발용이 고른 {best}: 시험용 {tally(TEST, veto(*best))} / 후보 그대로 {tally(TEST, lambda qi: prod(qi))}')
print(f'시험용 점수 차이(거부권 − 후보 그대로) 문제당 {sum(d) / len(d):+.3f} [{bs[49]:+.3f}, {bs[1949]:+.3f}]')
