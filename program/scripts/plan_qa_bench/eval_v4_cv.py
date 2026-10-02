# V4 비평(짚은 항목을 같은 E4B QAT 가 다시 확인, 확률 < τ 이면 「없음」) — 기존 5세트에서 세트 하나를 빼고 τ 를 골라 그 세트로 시험(참고용).
#  단위 = 정답 − 2×엉뚱한 답 − 0.05×(넘김 호출 + 비평 호출). 보조: 넘김이 항목을 짚은 경우에 비평 확률이 맞은 짚기와 틀린 짚기를 얼마나 가르는가(AUROC).
# 사용: python eval_v4_cv.py [--md 출력파일]
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
argv0 = sys.argv
sys.argv = ['x', 'e16d']
src = open(os.path.join(HERE, 'eval_router.py'), encoding='utf-8').read()
head = src[:src.index('# 문턱(개발용 44 로 선택)')]
G0 = {'__name__': 'er', '__file__': os.path.join(HERE, 'eval_router.py')}
exec(compile(head, 'er', 'exec'), G0)
sys.argv = argv0
SETS, G, run, pipe, grid, dev, LABELED, M, R, J = (G0[k] for k in ('SETS', 'G', 'run', 'pipe', 'grid', 'dev', 'LABELED', 'M', 'R', 'J'))
best = max(grid, key=lambda g: (pipe('heavy', dev, *g, M)[0] - 2 * pipe('heavy', dev, *g, M)[1] - 0.05 * pipe('heavy', dev, *g, M)[2], -g[0]))
lo, hi = best
VP = {w: {int(k): v for k, v in J(R(f'verify_{w}_gemma4_e4b-it-qat.json'))['p'].items()} for w in LABELED}
idx = {w: [i for i in range(len(SETS[w]['qs'])) if not (w == 'heavy' and SETS[w]['qs'][i].get('split') != 'held')] for w in LABELED}


def ev(w, tau):
    ok = bad = calls = ver = 0
    for i in idx[w]:
        p, u = run(w, i, lo, hi, M)
        if u and p is not None:
            ver += 1
            if VP[w].get(i, 1.0) < tau:
                p = None
        g = SETS[w]['qs'][i]['gold']
        ok += p == g
        bad += p is not None and p != g
        calls += u
    return ok, bad, calls, ver


taus = [round(0.05 * k, 2) for k in range(0, 20)]
out = [f'## V4 비평 — 기존 5세트 참고 · 앞단 e16d 문턱 {lo}/{hi} · 넘김 E4B QAT · 비평 E4B QAT', '| 시험 세트 | 고른 τ(나머지 4세트) | 비평 없음 정답/엉뚱/호출 | V4 정답/엉뚱/호출+비평 |', '|---|---:|---|---|']
tot0 = [0, 0, 0]
tot1 = [0, 0, 0, 0]
for w in LABELED:
    tr = [x for x in LABELED if x != w]
    sc = []
    for t in taus:
        a = [sum(v) for v in zip(*[ev(x, t) for x in tr])]
        sc.append((a[0] - 2 * a[1] - 0.05 * (a[2] + a[3]), -t, t))
    tau = max(sc)[2]
    b0 = ev(w, 0.0)
    b1 = ev(w, tau)
    tot0 = [a + b for a, b in zip(tot0, b0[:3])]
    tot1 = [a + b for a, b in zip(tot1, (b1[0], b1[1], b1[2] + b1[3]))]
    out.append(f'| {w} | {tau} | {b0[0]}/{b0[1]}/{b0[2]} | {b1[0]}/{b1[1]}/{b1[2]}+{b1[3]} |')
out.append(f'| **합** | | **{tot0[0]}**/{tot0[1]}/{tot0[2]} | **{tot1[0]}**/{tot1[1]}/{tot1[2]} |')
# 고정 τ 별 5세트 합(참고, 선택 아님)
out += ['', '### 고정 τ 별 5세트 합(선택하지 않은 참고)', '| τ | 정답 | 엉뚱한 답 | 비평 호출 |', '|---:|---:|---:|---:|']
for t in (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
    a = [sum(v) for v in zip(*[ev(x, t) for x in LABELED])]
    out.append(f'| {t} | {a[0]} | {a[1]} | {a[3]} |')
# AUROC: 넘김 호출로 항목을 짚은 문제에서 맞은 짚기(1) 대 틀린 짚기(0)
pos, neg = [], []
for w in LABELED:
    for i in idx[w]:
        p, u = run(w, i, lo, hi, M)
        if u and p is not None:
            (pos if p == SETS[w]['qs'][i]['gold'] else neg).append(VP[w].get(i, 1.0))
auc = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / max(1, len(pos) * len(neg))
out.append(f'\n넘김이 항목을 짚은 {len(pos) + len(neg)}개 중 맞은 짚기 {len(pos)} · 틀린 짚기 {len(neg)} — 비평 확률의 AUROC = {auc:.3f}(0.5 = 가르지 못함, 1 = 완벽)')
print('\n'.join(out))
if '--md' in argv0:
    open(argv0[argv0.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
