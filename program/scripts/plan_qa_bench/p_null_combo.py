# 짚기 모델의 「없음」 확률(p_null)로 오지목을 줄이는 오프라인 계산 — 사용자 제안(2026-10-07): FrogNano 가 오지목이라 판별하면 짚기 모델이 그 항목의 「없음」 확률을 높게 매겨 다시 검토.
#  구성: ①단독 문턱 — 짚기 모델이 항목을 골랐어도 p_null ≥ τ 이면 「없음」 ②결합 — FrogNano 가 「없음」일 때만 문턱을 τ_f 로 낮춤(τ_f = 0 이면 무조건 거부 = 앞의 거부권).
#  입력: results/d_test/d_test_lp_q4km_<시드>.jsonl (D, p_null 기록) · d_test_lp_d2_q4km_<시드>.jsonl (D2 잡담 1,000) · FrogNano: d_test_a_frognano.jsonl(D) · d_test_d2_frog.jsonl(D2). 서비스 기반 Q4_K_M, 시드 1·2·3.
#  사후 선택을 피하려고 D 를 문항 번호 i 의 짝수/홀수로 나눠 한쪽(개발)에서 고른 문턱을 다른 쪽(시험)과 D2(새 잡담)에서 확인한다.
# 사용: python p_null_combo.py   → results/p_null_combo.md
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')
D = os.path.join(HERE, 'results', 'd_test')


def load(name):
    d = {}
    for line in open(os.path.join(D, name), encoding='utf-8'):
        r = json.loads(line)
        d[r['i']] = r
    return d


SEEDS = {'시드 1': 'e4bt', '시드 2': 'e4bs2', '시드 3': 'e4bs3'}
lpD = {s: load(f'd_test_lp_q4km_{n}.jsonl') for s, n in SEEDS.items()}
lpD2 = {s: load(f'd_test_lp_d2_q4km_{n}.jsonl') for s, n in SEEDS.items()}
frogD, frogD2 = load('d_test_a_frognano.jsonl'), load('d_test_d2_frog.jsonl')
ids = [i for i, r in lpD['시드 1'].items() if r['type'] != 'compound_intent']
dev = [i for i in ids if i % 2 == 0]
tst = [i for i in ids if i % 2 == 1]
ids2 = sorted(lpD2['시드 1'])
GRID = [0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001, 1e-4, 1e-5, 1e-6]


def final(r, frog, tau, mode):
    p = r.get('pick')
    if p is None:
        return None
    pn = r.get('p_null') or 0.0
    if mode == 'plain':
        return None if pn >= tau else p
    return None if (frog.get('pick') is None and pn >= tau) else p     # frog 가 「없음」일 때만 문턱 tau (tau=0 → 거부권)


def stats(seed, subset, tau, mode):
    r_, nul, ans, fp, ok = lpD[seed], 0, 0, 0, 0
    tot = 0
    for i in subset:
        g = r_[i]['gold']
        f = final(r_[i], frogD[i], tau, mode)
        tot += (f == g)
        if g is None:
            nul += 1
            fp += f is not None
        else:
            ans += 1
            ok += f == g
    return tot / len(subset), fp / nul, ok / ans


def d2_fp(seed, tau, mode):
    return sum(1 for i in ids2 if final(lpD2[seed][i], frogD2[i], tau, mode) is not None) / len(ids2)


out = ['# 「없음」 확률 문턱 · FrogNano 결합 — 오프라인 계산(서비스 기반 Q4_K_M · 시드 3개)\n',
       '- **개발/시험 분할**: D(2,669문항)를 문항 번호 짝수(개발)·홀수(시험)로 나눠 표는 **시험 쪽**과 **D2 새 잡담 1,000문장**의 값이다. 문턱을 개발 쪽에서 고르는 방식은 맨 아래.',
       '- 열: D 시험쪽 전체 정답 / 오지목 / 정답 있는 질문 · D2 잡담 오지목. 시드 3개의 평균과 **범위**를 같이 적는다(전에는 D2 오지목 시드 1 · 2 = 6.5 · 15.3%).\n']
pn_picked = sorted((r.get('p_null') or 0.0) for s in SEEDS for i, r in lpD[s].items() if r.get('pick') is not None)
out.append(f'- 항목을 골랐을 때의 p_null 분포(전체 시드): 중앙 {statistics.median(pn_picked):.2e} · 90% {pn_picked[int(.9 * len(pn_picked))]:.2e} · 99% {pn_picked[int(.99 * len(pn_picked))]:.2e}\n')
out.append('| 구성 | 문턱 | 시드 1 (전체/오지목/정답있음 · D2) | 시드 2 | 시드 3 | 3시드 평균 · D2 오지목 범위 |')
out.append('|---|---|---|---|---|---|')


def rowfor(label, tau, mode):
    cells, d2s, alls, fps, anss = [], [], [], [], []
    for s in SEEDS:
        a, f, k = stats(s, tst, tau, mode)
        d2 = d2_fp(s, tau, mode)
        cells.append(f'{100 * a:.1f} / {100 * f:.1f} / {100 * k:.1f} · {100 * d2:.1f}')
        alls.append(a)
        fps.append(f)
        anss.append(k)
        d2s.append(d2)
    out.append(f'| {label} | {tau:g} | ' + ' | '.join(cells) + f' | 전체 {100 * statistics.mean(alls):.1f} · 정답있음 {100 * statistics.mean(anss):.1f} · D2 {100 * min(d2s):.1f}~{100 * max(d2s):.1f} |')


rowfor('단독(문턱 없음)', 2.0, 'plain')
for tau in GRID:
    rowfor('단독 문턱', tau, 'plain')
for tau in GRID[:9]:
    rowfor('FrogNano 가 「없음」일 때만 문턱', tau, 'frog')
rowfor('거부권(Frog 가 「없음」이면 무조건)', 0.0, 'frog')
# 개발 쪽에서 문턱 고르기: 3시드 평균 전체 정답이 최대인 τ(구성별)
out.append('\n**개발 쪽에서 고른 문턱**(3시드 평균 D 전체 정답 최대) → 시험쪽 · D2 에서의 값')
for mode, label in (('plain', '단독 문턱'), ('frog', 'FrogNano 결합')):
    best = max(GRID, key=lambda t: statistics.mean(stats(s, dev, t, mode)[0] for s in SEEDS))
    row = [stats(s, tst, best, mode) for s in SEEDS]
    d2 = [d2_fp(s, best, mode) for s in SEEDS]
    out.append(f'- {label}: τ = {best:g} → 시험쪽 전체 ' + ' · '.join(f'{100 * r[0]:.1f}' for r in row) + ' / 오지목 ' + ' · '.join(f'{100 * r[1]:.1f}' for r in row) + ' / 정답 있는 ' + ' · '.join(f'{100 * r[2]:.1f}' for r in row) + f' / D2 오지목 ' + ' · '.join(f'{100 * x:.1f}' for x in d2) + f' (범위 {100 * min(d2):.1f}~{100 * max(d2):.1f})')
out.append('\n- 한계: 서비스 기반(Q4_K_M) 시드 1·2·3 · 한 번의 결정적 실행, D 는 합성 + AI Hub 잡담이고 D2 는 시험·학습에 안 쓴 잡담. FrogNano 는 D 결과를 보고 고른 모델(사후 선택).')
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'p_null_combo.md'), 'w', encoding='utf-8').write(text)
print(text)
