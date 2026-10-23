# 가르친 E4B 의 「확신도」(답 토큰 확률의 곱)로 확신이 낮은 문제만 다른 모델에 넘기는 위임 모의 — 769문제(요청 둘 제외, mix8~12), 새 호출 없음.
#  입력: results/_pull/distill_eval/eval_e4bconf_<세트>.json (CONF=1 평가 — 같은 어댑터·같은 문제 · 문제마다 _confs) + 기존 시험 답(per_question.csv).
#  문턱 τ 는 「한 세트 빼고 정확도가 가장 높은 값을 고르고 그 세트에서 시험」(leave-one-set-out)으로만 판정한다. 위임 대상 구성원은 시험 전에 정했다(소형 먼저: Decider-12B · Winnow-12B, 참고로 큰 모델).
# 사용: python conf_delegation_769.py > results/conf_delegation_769.txt
import csv, json, math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
SETS = ['mix8', 'mix9', 'mix10', 'mix11', 'mix12']
sys.stdout.reconfigure(encoding='utf-8')


def fnum(x):
    return None if x in ('', None) else int(float(x))


rows = list(csv.DictReader(open(os.path.join(HERE, 'results/export/per_question.csv'), encoding='utf-8-sig')))
GOLD, TYPE, PICK = {}, {}, defaultdict(dict)
for r in rows:
    if r['set'] in SETS:
        k = (r['set'], int(r['q_index']))
        GOLD[k], TYPE[k] = fnum(r['gold']), r['q_type']
        PICK[r['model']][k] = fnum(r['pick'])
KEYS = [(s, i) for s in SETS for i in range(len(json.load(open(fixture(f'{s}.json'), encoding='utf-8'))['sets'][s]['qs']))]
KEYS = [k for k in KEYS if TYPE[k] != 'compound_intent']
assert len(KEYS) == 769
E4B, CONF, SAME = {}, {}, 0
for s in SETS:
    c = json.load(open(os.path.join(HERE, f'results/_pull/distill_eval/eval_e4bconf_{s}.json'), encoding='utf-8'))['e4bconf#lora']
    o = json.load(open(os.path.join(HERE, f'results/_pull/distill_eval/eval_r16e2_{s}.json'), encoding='utf-8'))['r16e2#lora']
    for i, p in enumerate(c['picks']):
        E4B[(s, i)] = p
        CONF[(s, i)] = c['_confs'][i]
        SAME += (p == o['picks'][i])
print(f'가르친 E4B 확신도 평가의 답이 앞선 평가(r16e2)의 답과 같은 문제: {SAME}/835 (탐욕 생성이라 같아야 한다)')


def find(prefix):
    c = [m for m in PICK if m.startswith(prefix)]
    assert len(c) == 1, (prefix, c)
    return c[0]


TARGETS = [('Decider-12B', find('Decider-12B bf16'), '소형'), ('Winnow-12B', find('Winnow-12B Q8'), '소형'), ('Jev-Omni 묶음', find('Jev-Omni 묶음'), '소형'),
           ('Gemma 26B', find('Gemma 4 26B'), '참고(큰 모델)'), ('Qwen3.8 27B', find('Qwen3.8 27B'), '참고(큰 모델)'), ('decider-chat 31B', find('decider-chat Gemma4-31B'), '참고(큰 모델)')]
ok = {k: E4B[k] == GOLD[k] for k in KEYS}
base = sum(ok.values())
print(f'가르친 E4B 단독 {base}/769 = {100 * base / 769:.2f}%')

# 확신도가 맞고 틀림을 얼마나 가르나 (AUROC)
pos = [CONF[k] for k in KEYS if ok[k]]
neg = [CONF[k] for k in KEYS if not ok[k]]
gt = sum(1 for n in neg for p in pos if p > n) + 0.5 * sum(1 for n in neg for p in pos if p == n)
print(f'확신도 AUROC(맞은 문제 {len(pos)} vs 틀린 문제 {len(neg)}) = {gt / (len(pos) * len(neg)):.3f} · 맞은 문제 확신도 평균 {sum(pos) / len(pos):.3f} · 틀린 문제 평균 {sum(neg) / len(neg):.3f}')
for lo, hi in ((0, .5), (.5, .8), (.8, .95), (.95, 1.01)):
    ks = [k for k in KEYS if lo <= CONF[k] < hi]
    if ks:
        print(f'  확신도 [{lo:.2f}, {min(hi, 1):.2f}): {len(ks):>4}문제 중 맞음 {sum(ok[k] for k in ks)} ({100 * sum(ok[k] for k in ks) / len(ks):.1f}%)')


def mcnemar(a, b):
    oa = sum(1 for k in KEYS if a[k] == GOLD[k] and b[k] != GOLD[k])
    ob = sum(1 for k in KEYS if b[k] == GOLD[k] and a[k] != GOLD[k])
    n = oa + ob
    if n == 0:
        return oa, ob, 1.0
    t = min(oa, ob)
    return oa, ob, min(1.0, 2 * sum(math.comb(n, i) for i in range(t + 1)) / 2 ** n)


GRID = [0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99]
print('\n## 위임: 확신도 < τ 이면 대상 모델의 답, 아니면 가르친 E4B 의 답')
for name, m, kind in TARGETS:
    print(f'\n[{name} — {kind}] 단독 {sum(PICK[m][k] == GOLD[k] for k in KEYS)}/769')
    best = {}
    for tau in GRID:
        r = {k: (PICK[m][k] if CONF[k] < tau else E4B[k]) for k in KEYS}
        n = sum(r[k] == GOLD[k] for k in KEYS)
        sent = sum(1 for k in KEYS if CONF[k] < tau)
        a, b, p = mcnemar(r, E4B)
        print(f'   τ={tau:<5} 넘김 {sent:>4} ({100 * sent / 769:4.1f}%) → {n}/769 = {100 * n / 769:.2f}% (E4B 대비 {a}:{b}, p={p:.3f})')
    # leave-one-set-out
    loso = {}
    taus = []
    for held in SETS:
        sc = {}
        for tau in GRID:
            sc[tau] = sum(1 for k in KEYS if k[0] != held and (PICK[m][k] if CONF[k] < tau else E4B[k]) == GOLD[k])
        bt = max(GRID, key=lambda t: (sc[t], -t))
        taus.append(bt)
        for k in KEYS:
            if k[0] == held:
                loso[k] = PICK[m][k] if CONF[k] < bt else E4B[k]
    n = sum(loso[k] == GOLD[k] for k in KEYS)
    sent = sum(1 for k in KEYS if loso[k] != E4B[k] or False)
    a, b, p = mcnemar(loso, E4B)
    called = 0
    for held, bt in zip(SETS, taus):
        called += sum(1 for k in KEYS if k[0] == held and CONF[k] < bt)
    print(f'   ▶ leave-one-set-out(고른 τ: {", ".join(str(t) for t in taus)}): {n}/769 = {100 * n / 769:.2f}% (E4B 대비 {a}:{b}, p={p:.3f}) · 넘긴 문제 {called} ({100 * called / 769:.1f}%)')
