# 로그확률 확신도로 「모르면 답하지 않기」 — 넘김 모델(E4B)의 답에 확신도(자기 토큰 확률)가 문턱 미만이면 「없음」으로 처리한다(투표·합의·상위 모델 호출 없음).
#  문턱 τc 는 (lo, hi) 와 함께 heavy 개발용 44문제로만 고른다. eval_night.py 의 앞단·구조·문턱 탐색 코드를 그대로 쓴다.
# 사용: python eval_conf.py [넘김 모델=gemma4:e4b]
import json, os, sys, io, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
FB = sys.argv[1] if len(sys.argv) > 1 else 'gemma4:e4b'
src = open(os.path.join(HERE, 'eval_night.py'), encoding='utf-8').read()
head = src[:src.index('grid = [')]
ns = {'__name__': 'en', '__file__': os.path.join(HERE, 'eval_night.py')}
argv_bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'eval_night_head', 'exec'), ns)
sys.argv = argv_bak
SETS, G, run, analyze, rule_slots, resolve, top = (ns[k] for k in ('SETS', 'G', 'run', 'analyze', 'rule_slots', 'resolve', 'top'))
R = lambda *a: os.path.join(HERE, 'results', *a)
CONF = {}
for j in SETS:
    f = R(f'llm_{j}_lp_out.json')
    if os.path.exists(f):
        d = json.load(open(f, encoding='utf-8'))
        if FB in d:
            CONF[j] = d[FB]
            G[j][FB + '#lp'] = d[FB]['picks']        # 같은 실행의 답(온도 0 이라 기본 실행과 같아야 한다)
missing = [j for j in SETS if j not in CONF]
if missing:
    raise SystemExit(f'확신도 파일 없음: {missing}')


def run_c(job, i, lo, hi, tc):
    st = SETS[job]
    x = st['qs'][i]
    p, used = run(job, i, lo, hi, FB + '#lp')
    if used and p is not None:
        c = CONF[job]['conf'][i]
        if c is not None and c < tc:
            return None, used
    return p, used


def pipe(job, idx, lo, hi, tc):
    qs = SETS[job]['qs']
    ok = bad = calls = 0
    for i in idx:
        p, used = run_c(job, i, lo, hi, tc)
        g = qs[i]['gold']
        ok += (p == g); bad += (p is not None and p != g); calls += used
    return ok, bad, calls


grid = [(lo, hi, tc) for lo in (0.15, 0.25, 0.35) for hi in (0.5, 0.6, 0.7) for tc in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95)]
dev = [i for i, x in enumerate(SETS['heavy']['qs']) if x['split'] == 'dev']
held = [i for i, x in enumerate(SETS['heavy']['qs']) if x['split'] == 'held']
IDX = {'heavy': held, 'mix4': list(range(88)), 'mix5': list(range(88))}
score = lambda g: (pipe('heavy', dev, *g)[0] - 2 * pipe('heavy', dev, *g)[1], -g[2])   # 정답 − 2×엉뚱, 동률이면 문턱이 낮은 쪽
best = max(grid, key=score)
base = max([g for g in grid if g[2] == 0.0], key=score)
print(f'## 확신도 기권 — 넘김 {FB} · 개발용으로 고른 문턱 (lo, hi, τc)')
for name, g in (('확신도 기권 없음(τc=0)', base), ('확신도 기권 적용', best)):
    r = [pipe(j, IDX[j], *g) for j in SETS]
    print(f"  {name}: lo={g[0]} hi={g[1]} τc={g[2]} → heavy {r[0][0]} · mix4 {r[1][0]} · mix5 {r[2][0]} = 합 {sum(x[0] for x in r)}/264 · 엉뚱한 답 합 {sum(x[1] for x in r)}")
print('  τc 별(lo, hi 는 위 기권 없음 선택으로 고정):')
for tc in (0.0, 0.5, 0.7, 0.8, 0.9, 0.95):
    r = [pipe(j, IDX[j], base[0], base[1], tc) for j in SETS]
    print(f"    τc={tc}: heavy {r[0][0]} · mix4 {r[1][0]} · mix5 {r[2][0]} = {sum(x[0] for x in r)} · 엉뚱 {sum(x[1] for x in r)}")
