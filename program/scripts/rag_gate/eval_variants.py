# 임베딩 대상 변형(A 직원용 본문=운영 · B 고객용 문장 · C 절 제목+문장 · D 본문+문장 · E 문서 제목+절 제목+문장)별 규정 검색 종단 채점.
#  운영식 = 임베딩 상위 3개 절 중 점수 ≥ τ 인 것의 고객용 문장 상위 2개를 보임(없으면 「못 찾음」). 점수 = 답 있음 정답 줄 보임 +1 · 틀린 줄만 −2 · 답 없는데 답함 −2 (비슷하지만 다름은 따로 셈).
#  τ 는 짝수 번째(개발용)로만 고르고 홀수 번째(시험용)로 판정, 운영(A, τ 0.55) 대비 시험용 문제당 점수 차이와 95% 구간(복원추출 2000, 시드 20261001).
# 사용: 폴더 안에 fixtures/rag_questions.json · fixtures/policy_chunks.json · results/rag_embed_variants.json 이 있어야 한다. python eval_variants.py [--md 출력파일]
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
J = lambda *a: json.load(open(os.path.join(HERE, *a), encoding='utf-8'))
Q = J('fixtures', 'rag_questions.json')['questions']
CH = J('fixtures', 'policy_chunks.json')
LINE = {c['source'] for c in CH if c['line']}
V = J('results', 'rag_embed_variants.json')
SRC = V['sources']
N = len(Q)
DEV = [i for i in range(N) if i % 2 == 0]
TEST = [i for i in range(N) if i % 2 == 1]
ans = [i for i in range(N) if Q[i]['type'] == 'answerable']


def prod(sims, qi, tau, topk=3, top=2):
    order = sorted(range(len(SRC)), key=lambda i: -sims[qi][i])[:topk]
    return [SRC[i] for i in order if sims[qi][i] >= tau and SRC[i] in LINE][:top]


def outcome(qi, shown):
    q = Q[qi]
    if q['type'] == 'answerable':
        if not shown:
            return 'miss', 0
        return ('correct', 1) if set(shown) & set(q['gold']) else ('wrong', -2)
    return ('abstain', 0) if not shown else ('false', -2)


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


out = [f'## 임베딩 대상별 규정 검색 — {N}문제(답 있음 {len(ans)}, 답 없음 {sum(q["type"] in ("uncovered", "offtopic", "travel_other") for q in Q)}, 비슷하지만 다름 {sum(q["type"] == "near_miss" for q in Q)})',
       '| 임베딩 대상 | @1 | @3 | @5 | τ(개발용) | 시험용 정답/틀린줄/못찾음/없음에답 | 시험용 점수 | 전체 정답/틀린줄/못찾음/없음에답 | 전체 점수 |', '|---|---:|---:|---:|---:|---|---:|---|---:|']
taus = [round(0.30 + 0.01 * k, 2) for k in range(50)]
chosen = {}
for name, sims in V['variants'].items():
    rec = {}
    for k in (1, 3, 5):
        rec[k] = sum(bool(set([SRC[i] for i in sorted(range(len(SRC)), key=lambda i: -sims[qi][i]) if SRC[i] in LINE][:k]) & set(Q[qi]['gold'])) for qi in ans)
    tb = max(taus, key=lambda t: tally(DEV, lambda qi: prod(sims, qi, t))['score'])
    chosen[name] = tb
    ct, ca = tally(TEST, lambda qi: prod(sims, qi, tb)), tally(range(N), lambda qi: prod(sims, qi, tb))
    nn = lambda c: c['false']
    out.append(f"| {name} | {rec[1]} | {rec[3]} | {rec[5]} | {tb:.2f} | {ct['correct']}/{ct['wrong']}/{ct['miss']}/{ct['false']} | {ct['score']} | {ca['correct']}/{ca['wrong']}/{ca['miss']}/{ca['false']} | {ca['score']} |")
simsA = V['variants'][[k for k in V['variants'] if k.startswith('A')][0]]
out.append('')
for name, sims in V['variants'].items():
    if name.startswith('A'):
        continue
    d = [outcome(qi, prod(sims, qi, chosen[name]))[1] - outcome(qi, prod(simsA, qi, 0.55))[1] for qi in TEST if Q[qi]['type'] != 'near_miss']
    r = random.Random(20261001)
    bs = sorted(sum(r.choice(d) for _ in d) / len(d) for _ in range(2000))
    out.append(f"{name} (τ {chosen[name]}) − 운영(A, 0.55): 시험용 문제당 점수 {sum(d) / len(d):+.3f} [{bs[49]:+.3f}, {bs[1949]:+.3f}]")
print('\n'.join(out))
if '--md' in sys.argv:
    open(sys.argv[sys.argv.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
