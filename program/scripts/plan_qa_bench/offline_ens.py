# 저장된 결정 모델 확률·짚은 답으로 오프라인 계산 — 서버를 다시 돌리지 않는다.
#  ① 모델별 직접 정확도(규칙 단계 없이 모든 문제를 모델 하나가 푼 값)
#  ② 확률 평균 앙상블(결정 모델 2~4개) — 고르는 세트(개발)와 시험 세트를 나눈다
#  ③ 확신 기반 위임: 모델 A 의 확신(최고 확률)이 τ 미만이면 모델 B 로 넘긴다
#  ④ 짚은 답 다수결
# 사용: python offline_ens.py --dev mix8,mix9 --test mix10[,mix11] [--md 출력파일]
import itertools, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda n: os.path.join(HERE, 'results', n)
FX = lambda n: os.path.join(HERE, 'fixtures', n)
argv = sys.argv
DEV = argv[argv.index('--dev') + 1].split(',') if '--dev' in argv else ['mix8', 'mix9']
TEST = argv[argv.index('--test') + 1].split(',') if '--test' in argv else ['mix10']
OUT = argv[argv.index('--md') + 1] if '--md' in argv else None
ALL = DEV + TEST
GOLD = {w: [x['gold'] for x in json.load(open(FX(f'{w}.json'), encoding='utf-8'))['sets'][w]['qs']] for w in ALL}

# 확률을 읽는 결정 모델(라벨, 파일 태그)
DEC = [('Decider-12B bf16', 'decider12bl'), ('Decider-12B 8비트', 'decider12bq8'), ('decider-chat 31B', 'decider31bl'),
       ('OpenJev 26B', 'openjev26b'), ('pplx 27B', 'pplx27b'), ('Cygnet', 'cygnet'), ('Hopper 12B', 'hopper12b'),
       ('Decider-35B-A3B', 'decider35bl'), ('decider-chat Qwen3.6-27B', 'decider27ql'), ('Winnow-12B', 'winnow12b')]
LLM = [('Gemma 26B', 'gemma4:26b-a4b-it-q4_K_M'), ('Qwen3.8 27B', 'qwen3.8:27b'), ('Gemma 12B', 'gemma4:12b'), ('E4B QAT', 'gemma4:e4b-it-qat')]


def pick_of(key):
    return int(key.split('_')[1]) if key.startswith('item_') else None


PROB = {}    # 라벨 → {세트: [ {키: 확률} ]}
for lab, tag in DEC:
    d = {}
    for w in ALL:
        f = R(f'dec_{tag}_{w}.json')
        if not os.path.exists(f):
            break
        rows = json.load(open(f, encoding='utf-8'))[w]['rows']
        if len(rows) != len(GOLD[w]) or any(not r['probs'] for r in rows):
            break
        d[w] = [r['probs'] for r in rows]
    else:
        PROB[lab] = d

PICK = {}    # 라벨 → {세트: [id|None]}
for lab, key in LLM:
    d = {}
    for w in ALL:
        f = R(f'llm_{w}_out.json')
        if not os.path.exists(f):
            break
        o = json.load(open(f, encoding='utf-8'))
        if key not in o or len(o[key]['picks']) != len(GOLD[w]):
            break
        d[w] = o[key]['picks']
    else:
        PICK[lab] = d
for lab, d in PROB.items():           # 결정 모델의 1순위도 짚은 답으로 쓴다
    PICK[lab] = {w: [pick_of(max(p, key=p.get)) for p in rows] for w, rows in d.items()}


def acc(picks, ws):
    ok = sum(int(a == g) for w in ws for a, g in zip(picks[w], GOLD[w]))
    return ok, sum(len(GOLD[w]) for w in ws)


def norm(p):
    s = sum(p.values())
    return {k: v / s for k, v in p.items()} if s > 0 else p


def avg_pick(labs, w):
    out = []
    for i in range(len(GOLD[w])):
        t = {}
        for lab in labs:
            for k, v in norm(PROB[lab][w][i]).items():
                t[k] = t.get(k, 0.0) + v
        out.append(pick_of(max(t, key=t.get)))
    return out


L = []
P = lambda s='': (print(s), L.append(s))
P(f'## 오프라인 계산 — 개발 {"+".join(DEV)} · 시험 {"+".join(TEST)}')
P()
P('### ① 모델별 직접 정확도')
P()
P('| 모델 | ' + ' | '.join(ALL) + ' | 개발 | 시험 |')
P('|---|' + '---|' * (len(ALL) + 2))
for lab, d in sorted(PICK.items(), key=lambda kv: -acc(kv[1], TEST)[0] / acc(kv[1], TEST)[1]):
    cells = [f'{acc(d, [w])[0]}/{acc(d, [w])[1]}' for w in ALL]
    a, b = acc(d, DEV), acc(d, TEST)
    P(f'| {lab} | ' + ' | '.join(cells) + f' | {a[0]}/{a[1]} = {100 * a[0] / a[1]:.1f}% | {b[0]}/{b[1]} = {100 * b[0] / b[1]:.1f}% |')

# ---------- ② 확률 평균 앙상블 ----------
labs = list(PROB)
P()
P(f'### ② 확률 평균 앙상블 — 후보 모델 {len(labs)}개({", ".join(labs)}), 크기 2~4 모든 조합')
P()
res = []
for n in (2, 3, 4):
    for c in itertools.combinations(labs, n):
        pk = {w: avg_pick(c, w) for w in ALL}
        res.append((c, acc(pk, DEV), acc(pk, TEST)))
P(f'조합 {len(res)}개를 개발 세트로 순위 매겼다. 개발 정확도 상위 8개와 그 시험 결과:')
P()
P('| 조합 | 개발 | 시험 |')
P('|---|---|---|')
res.sort(key=lambda r: (-r[1][0], -r[2][0]))
best_single = max(((lab, acc(PICK[lab], DEV)) for lab in labs), key=lambda x: x[1][0])
for c, a, b in res[:8]:
    P(f'| {" + ".join(c)} | {a[0]}/{a[1]} = {100 * a[0] / a[1]:.1f}% | {b[0]}/{b[1]} = {100 * b[0] / b[1]:.1f}% |')
c0, a0, b0 = res[0]
sb = acc(PICK[best_single[0]], TEST)
P()
P(f'개발 1위 조합 시험 {b0[0]}/{b0[1]}. 개발 1위 단일 모델({best_single[0]}) 시험 {sb[0]}/{sb[1]}.')

# ---------- ③ 확신 기반 위임 ----------
P()
P('### ③ 확신 기반 위임 — 모델 A 의 최고 확률이 τ 이상이면 A 의 답, 아니면 모델 B 의 답')
P()
GRID = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
for a_lab in labs:
    for b_lab in PICK:
        if b_lab == a_lab:
            continue
        rows = []
        for tau in GRID:
            pk = {}
            for w in ALL:
                pk[w] = [pick_of(max(p, key=p.get)) if max(norm(p).values()) >= tau else PICK[b_lab][w][i] for i, p in enumerate(PROB[a_lab][w])]
            rows.append((tau, acc(pk, DEV), acc(pk, TEST)))
        bt = max(rows, key=lambda r: r[1][0])
        P(f'- A={a_lab} → B={b_lab}: 개발에서 고른 τ={bt[0]} 개발 {bt[1][0]}/{bt[1][1]} · 시험 {bt[2][0]}/{bt[2][1]}  (A 단독 시험 {acc(PICK[a_lab], TEST)[0]})')

# ---------- ④ 짚은 답 다수결 ----------
P()
P('### ④ 짚은 답 다수결(셋·다섯 모델) — 동률이면 첫째 모델')
P()
cands = list(PICK)
rows = []
for n in (3, 5):
    for c in itertools.combinations(cands, n):
        pk = {}
        for w in ALL:
            out = []
            for i in range(len(GOLD[w])):
                cnt = {}
                for lab in c:
                    a = PICK[lab][w][i]
                    cnt[a] = cnt.get(a, 0) + 1
                top = max(cnt.values())
                win = [a for a, v in cnt.items() if v == top]
                out.append(win[0] if len(win) == 1 else PICK[c[0]][w][i])
            pk[w] = out
        rows.append((c, acc(pk, DEV), acc(pk, TEST)))
rows.sort(key=lambda r: (-r[1][0], -r[2][0]))
P(f'조합 {len(rows)}개. 개발 상위 6개:')
P()
P('| 조합 | 개발 | 시험 |')
P('|---|---|---|')
for c, a, b in rows[:6]:
    P(f'| {" + ".join(c)} | {a[0]}/{a[1]} = {100 * a[0] / a[1]:.1f}% | {b[0]}/{b[1]} = {100 * b[0] / b[1]:.1f}% |')

if OUT:
    open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
