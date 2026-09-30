# 통합 채점 — 세 세트(heavy 판정 88 · mix4 88 · mix5 88) 각각에서 모델 후보별 「직접 짚기」와 「앞단 + 구조 + 넘김 모델」 종단을 한 표로.
#  앞단 = 학습 임베딩 0.6B 의 점수(기본 e16c). 문턱(lo·hi)은 넘김 모델마다 heavy 개발용 44문제로만 고른다(mix4·mix5 로는 고르지 않는다).
#  넘김 모델 후보 = results/llm_<세트>_out.json(올라마) + gepa_e4b_<세트>.json + ft_pointer_<이름>_<세트>.json(HF 미세조정·제로샷) 중 세 세트에 모두 있는 것.
# 사용: python eval_night.py [FT 점수 키=ft/emb_e16c] [heavy·mix4 점수 파일] [mix5 점수 파일] [--md 출력파일]
import glob, json, os, sys
from collections import defaultdict
from clauses import analyze
from rule_slots import rule_slots
from slot_lookup import resolve

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda *a: os.path.join(HERE, 'results', *a)
args = [a for a in sys.argv[1:] if not a.startswith('--')]
KEY = args[0] if args else 'ft/emb_e16c'
F_HM = args[1] if len(args) > 1 else R('ft_e16c_scores.json')
F_M5 = args[2] if len(args) > 2 else R('ft_e16c_mix5_scores.json')
J = lambda f: json.load(open(f, encoding='utf-8'))
SETS = {j: J(os.path.join(HERE, 'fixtures', f'{j}.json'))['sets'][j] for j in ('heavy', 'mix4', 'mix5')}
pairs_hm = J(os.path.join(HERE, 'fixtures', 'pairs_experts.json'))
pairs_5 = J(os.path.join(HERE, 'fixtures', 'pairs_mix5.json'))
S = defaultdict(dict)
for pr, f in ((pairs_hm, F_HM), (pairs_5, F_M5)):
    for p, v in zip(pr, J(f)[KEY]):
        S[(p['set'], p['qi'])][p['item']] = v
G = {}
for j in SETS:
    G[j] = {}
    if os.path.exists(R(f'llm_{j}_out.json')):
        for m, v in J(R(f'llm_{j}_out.json')).items():
            if not m.startswith('_') and '#' not in m and isinstance(v, dict) and 'picks' in v:
                G[j][m] = v['picks']
    if os.path.exists(R(f'gepa_e4b_{j}.json')):
        G[j]['gepa_e4b'] = J(R(f'gepa_e4b_{j}.json'))['picks']
    for f in glob.glob(R(f'ft_pointer_*_{j}.json')):
        tag = os.path.basename(f)[len('ft_pointer_'):-len(f'_{j}.json')]
        G[j]['ftp_' + tag] = J(f)['picks']
models = sorted(set.intersection(*[set(G[j]) for j in SETS]))


def top(job, kind, i):
    d = S.get((f'{job}_{kind}', i))
    if not d:
        return None, 0.0
    k = max(d, key=d.get)
    return k, d[k]


def run(job, i, lo, hi, fb, tau_a=0.4):
    st = SETS[job]
    qs, items = st['qs'], st['items']
    x = qs[i]
    a = analyze(x['q'])
    rs = rule_slots(a['tt'], items)
    if rs['day'] is None:
        rs['day'] = rule_slots(x['q'], items)['day']
    anchor = None
    if rs['rel'] is not None:
        k, p = top(job, 'excl' if a['negation'] else 'tt', i)
        anchor = k if p >= tau_a else None
    slots = {k: rs[k] for k in ('day', 'pos', 'kind', 'meal', 'rel', 'kw', 'nextday')}
    slots['anchor'] = anchor
    r = resolve(items, slots)
    if r[0] == 'item':
        return r[1], False
    if r[0] == 'none':
        return None, False
    llm = G[job][fb][i]
    if x['history']:
        return llm, True
    k, p = top(job, 'tt', i)
    if p >= hi:
        return k, False
    if p < lo:
        return None, False
    return llm, True


def pipe(job, idx, lo, hi, fb):
    qs = SETS[job]['qs']
    ok = bad = calls = 0
    for i in idx:
        p, used = run(job, i, lo, hi, fb)
        g = qs[i]['gold']
        ok += (p == g); bad += (p is not None and p != g); calls += used
    return ok, bad, calls


def direct(job, idx, fb):
    qs = SETS[job]['qs']
    return sum(G[job][fb][i] == qs[i]['gold'] for i in idx)


grid = [(lo, hi) for lo in (0.15, 0.25, 0.3, 0.35, 0.4, 0.45) for hi in (0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75) if lo < hi]
dev = [i for i, x in enumerate(SETS['heavy']['qs']) if x['split'] == 'dev']
held = [i for i, x in enumerate(SETS['heavy']['qs']) if x['split'] == 'held']
allm = list(range(88))
IDX = {'heavy': held, 'mix4': allm, 'mix5': allm}
rows = []
for m in models:
    best = max(grid, key=lambda g: (pipe('heavy', dev, *g, m)[0] - 2 * pipe('heavy', dev, *g, m)[1] - 0.05 * pipe('heavy', dev, *g, m)[2], -g[0]))
    d = [direct(j, IDX[j], m) for j in SETS]
    p = [pipe(j, IDX[j], *best, m) for j in SETS]
    rows.append((m, d, p, best))
rows.sort(key=lambda r: -sum(x[0] for x in r[2]))
out = [f'## 통합 채점 — 앞단 {KEY} · 문턱은 넘김 모델마다 heavy 개발용 44 로 선택 · 세 세트(각 88) 각 1회',
       '| 넘김 모델 | 직접 짚기 heavy/mix4/mix5 (합 264) | 종단 heavy/mix4/mix5 | 종단 합 264 | 넘김 호출(mix5) | 문턱 lo/hi |', '|---|---|---|---:|---:|---|']
for m, d, p, b in rows:
    out.append(f"| {m} | {d[0]}/{d[1]}/{d[2]} ({sum(d)}) | {p[0][0]}/{p[1][0]}/{p[2][0]} | **{sum(x[0] for x in p)}** ({sum(x[0] for x in p) / 264:.1%}) | {p[2][2]}/88 | {b[0]}/{b[1]} |")
print('\n'.join(out))
if '--md' in sys.argv:
    open(sys.argv[sys.argv.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
