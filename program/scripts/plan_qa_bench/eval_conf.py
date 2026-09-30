# 확신도 기권 채점 — 넘김 모델의 답에 붙은 확신도(자기 토큰 확률, 올라마 logprobs 또는 HF generate 점수)가 τc 미만이면 「없음」으로 처리한다.
#  투표·합의·상위 모델 호출은 없다. 앞단·구조·문턱(lo, hi) 탐색은 eval_night.py 코드를 그대로 쓰고, τc 는 (lo, hi) 와 함께 heavy 개발용 44문제로 고른다.
#  확신도 출처: 올라마 gemma4:e4b → llm_<세트>_lp_out.json · 「hint_gemma4:e4b」 → llm_<세트>_hint_lp_out.json · 「ftp_<이름>」 → ft_pointer_<이름>_<세트>.json 의 conf
# 사용: python eval_conf.py [넘김 모델 이름 ...]   (기본: gemma4:e4b hint_gemma4:e4b 와 conf 가 있는 ftp_ 모델 전부)
import contextlib, glob, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda *a: os.path.join(HERE, 'results', *a)
names = sys.argv[1:]
src = open(os.path.join(HERE, 'eval_night.py'), encoding='utf-8').read()
head = src[:src.index('grid = [')]
ns = {'__name__': 'en', '__file__': os.path.join(HERE, 'eval_night.py')}
argv_bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'eval_night_head', 'exec'), ns)
sys.argv = argv_bak
SETS, G, run = ns['SETS'], ns['G'], ns['run']


def load_conf(job, name):
    if name == 'gemma4:e4b':
        f = R(f'llm_{job}_lp_out.json')
        d = json.load(open(f, encoding='utf-8')).get(name) if os.path.exists(f) else None
    elif name.startswith('hint_'):
        f = R(f'llm_{job}_hint_lp_out.json')
        d = json.load(open(f, encoding='utf-8')).get(name[5:]) if os.path.exists(f) else None
    elif name.startswith('ftp_'):
        f = R(f'ft_pointer_{name[4:]}_{job}.json')
        d = json.load(open(f, encoding='utf-8')) if os.path.exists(f) else None
    else:
        d = None
    if d and d.get('conf') and len(d['conf']) == len(d['picks']):
        return d
    return None


if not names:
    cand = ['gemma4:e4b', 'hint_gemma4:e4b'] + ['ftp_' + os.path.basename(f)[len('ft_pointer_'):-len('_heavy.json')] for f in sorted(glob.glob(R('ft_pointer_*_heavy.json')))]
    names = [n for n in cand if all(load_conf(j, n) for j in SETS)]
IDX = {'heavy': [i for i, x in enumerate(SETS['heavy']['qs']) if x['split'] == 'held'], 'mix4': list(range(88)), 'mix5': list(range(88))}
DEV = [i for i, x in enumerate(SETS['heavy']['qs']) if x['split'] == 'dev']
print('## 확신도 기권 — 넘김 모델별(문턱은 heavy 개발용 44 로 선택, 264문제 합)')
print('| 넘김 모델 | τc=0(기권 없음) 정답/엉뚱 | 개발용 선택 (lo,hi,τc) → 정답/엉뚱 | τc=0.7 정답/엉뚱 | τc=0.8 정답/엉뚱 | 확신도 AUROC(heavy 판정) |')
print('|---|---|---|---|---|---|')
for name in names:
    C = {j: load_conf(j, name) for j in SETS}
    tmp = name + '#c'
    for j in SETS:
        G[j][tmp] = C[j]['picks']

    def pipe(job, idx, lo, hi, tc):
        qs = SETS[job]['qs']
        ok = bad = 0
        for i in idx:
            p, used = run(job, i, lo, hi, tmp)
            if used and p is not None:
                c = C[job]['conf'][i]
                if c is not None and c < tc:
                    p = None
            g = qs[i]['gold']
            ok += (p == g); bad += (p is not None and p != g)
        return ok, bad

    grid = [(lo, hi, tc) for lo in (0.15, 0.25, 0.35) for hi in (0.5, 0.6, 0.7) for tc in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95)]
    sc = lambda g: (pipe('heavy', DEV, *g)[0] - 2 * pipe('heavy', DEV, *g)[1], -g[2])
    best = max(grid, key=sc)
    base = max([g for g in grid if g[2] == 0.0], key=sc)
    tot = lambda g: tuple(map(sum, zip(*[pipe(j, IDX[j], *g) for j in SETS])))
    a, b = tot(base), tot(best)
    t7, t8 = tot((base[0], base[1], 0.7)), tot((base[0], base[1], 0.8))
    # 확신도 AUROC (heavy 판정에서 직접 짚기의 정답·오답 구분)
    qs = SETS['heavy']['qs']
    pos = [C['heavy']['conf'][i] for i in IDX['heavy'] if C['heavy']['picks'][i] == qs[i]['gold'] and C['heavy']['conf'][i] is not None]
    neg = [C['heavy']['conf'][i] for i in IDX['heavy'] if C['heavy']['picks'][i] != qs[i]['gold'] and C['heavy']['conf'][i] is not None]
    auc = sum((x > y) + (x == y) / 2 for x in pos for y in neg) / max(1, len(pos) * len(neg))
    print(f"| {name} | {a[0]}/{a[1]} | ({best[0]},{best[1]},{best[2]}) → {b[0]}/{b[1]} | {t7[0]}/{t7[1]} | {t8[0]}/{t8[1]} | {auc:.2f} |")
