# 앞단 v3(e16d, AI Hub 일상 대화 잡담 정답 없음 + 점수 상하한 + 말투 변형) 대 e16c — 연구 문서 §39 사전 등록대로.
#  넘김 = E4B QAT. 문턱(lo·hi)은 두 앞단 모두 heavy 개발용 44문제로만 고른다(eval_night 와 같은 격자·규칙). 시험 = mix6 130 + mix7 173(학습에 쓰지 않은 세트).
#  보조: 같은 문턱에서 mix 별 정답, 이름 없는 설명 유형, 넘김 호출 비율, 잡담 3,000개의 LLM 넘김 비율과 E4B 가 잡담에 항목을 답한 비율(앞 1,500개).
# 사용: python eval_front_v3.py [--md 출력파일]
import contextlib, io, json, math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda *a: os.path.join(HERE, 'results', *a)
J = lambda f: json.load(open(f, encoding='utf-8'))
M = 'gemma4:e4b-it-qat'


def load(tag):
    src = open(os.path.join(HERE, 'eval_night.py'), encoding='utf-8').read()
    head = src[:src.index('rows = []')]
    ns = {'__name__': 'en', '__file__': os.path.join(HERE, 'eval_night.py')}
    bak = sys.argv
    sys.argv = ['x', f'ft/emb_{tag}', R(f'ft_{tag}_scores.json'), R(f'ft_{tag}_mix5_scores.json')]
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(head, 'eval_night_head', 'exec'), ns)
    sys.argv = bak
    S, G, SETS = ns['S'], ns['G'], ns['SETS']
    for w in ('mix6', 'mix7'):
        SETS[w] = J(os.path.join(HERE, 'fixtures', f'{w}.json'))['sets'][w]
        for p, v in zip(J(os.path.join(HERE, 'fixtures', f'pairs_{w}.json')), J(R(f'ft_{tag}_{w}_scores.json'))[f'ft/emb_{tag}']):
            S[(p['set'], p['qi'])][p['item']] = v
        G[w] = {m: v['picks'] for m, v in J(R(f'llm_{w}_out.json')).items() if isinstance(v, dict) and 'picks' in v and '#' not in m and not m.startswith('_')}
    return ns


def ci(a, b, n):
    d = [1] * a + [-1] * b + [0] * (n - a - b)
    r = random.Random(20261001)
    bs = sorted(sum(r.choice(d) for _ in range(n)) / n * 100 for _ in range(2000))
    return (a - b) / n * 100, bs[49], bs[1949]


def pexact(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


res = {}
for tag in ('e16c', 'e16d'):
    ns = load(tag)
    SETS, run, pipe, grid, dev = ns['SETS'], ns['run'], ns['pipe'], ns['grid'], ns['dev']
    best = max(grid, key=lambda g: (pipe('heavy', dev, *g, M)[0] - 2 * pipe('heavy', dev, *g, M)[1] - 0.05 * pipe('heavy', dev, *g, M)[2], -g[0]))
    preds = {w: [run(w, i, best[0], best[1], M) for i in range(len(SETS[w]['qs']))] for w in ('mix6', 'mix7')}
    res[tag] = {'best': best, 'preds': preds, 'SETS': SETS, 'ns': ns}
out = ['## 앞단 v3(e16d) 대 e16c — 문턱은 heavy 개발용 44 로 선택, 시험 = mix6 + mix7 (303문제), 넘김 E4B QAT']
out.append('| 앞단 | 선택된 문턱 lo/hi | mix6 정답 | mix7 정답 | 합 303 | 엉뚱한 답 | 넘김 호출 | 이름 없는 설명 정답 |')
out.append('|---|---|---:|---:|---:|---:|---:|---:|')
OK = {}
for tag in ('e16c', 'e16d'):
    r = res[tag]
    SETS = r['SETS']
    row = []
    tot = bad = calls = nl = nl_n = 0
    for w in ('mix6', 'mix7'):
        qs = SETS[w]['qs']
        ok = 0
        okv = []
        for (p, u), x in zip(r['preds'][w], qs):
            g = x['gold']
            okv.append(p == g)
            ok += p == g
            bad += p is not None and p != g
            calls += u
            if x['type'] == 'nameless_description':
                nl_n += 1
                nl += p == g
        OK[(tag, w)] = okv
        row.append(ok)
        tot += ok
    n = sum(len(SETS[w]['qs']) for w in ('mix6', 'mix7'))
    out.append(f"| {tag} | {r['best'][0]}/{r['best'][1]} | {row[0]} | {row[1]} | **{tot}** ({tot / n:.1%}) | {bad} | {calls}/{n} ({calls / n:.0%}) | {nl}/{nl_n} |")
a = sum(x and not y for w in ('mix6', 'mix7') for x, y in zip(OK[('e16d', w)], OK[('e16c', w)]))
b = sum(y and not x for w in ('mix6', 'mix7') for x, y in zip(OK[('e16d', w)], OK[('e16c', w)]))
d, lo, hi = ci(a, b, 303)
out.append(f'\n짝지은 차이(e16d − e16c, 303문제): {d:+.1f}%p [{lo:+.1f}, {hi:+.1f}] (e16d만 {a} : e16c만 {b}, p={pexact(a, b):.3f})')
# 잡담
D = os.path.join(HERE, '..', '..', '..', 'datasets', 'travel', '020.주제별 텍스트 일상 대화 데이터', 'processed')
E4 = J(R('chat_llm_mix7_gemma4_e4b-it-qat.json'))['picks']
out += ['', '## 잡담 3,000개(mix7 일정) — 각 앞단이 고른 문턱에서', '| 앞단 | 문턱 lo/hi | LLM 으로 넘김 | 앞단이 항목으로 확정 | E4B 가 항목으로 답함(앞 1,500 중) → 잡담 오답 비율 |', '|---|---|---:|---:|---|']
for tag, suf in (('e16c', ''), ('e16d', '_e16d')):
    fr = J(R(f'chat_front_mix7{suf}.json'))
    mx = [max(r) for r in fr['sims']]
    lo_, hi_ = res[tag]['best']
    n = len(mx)
    routed = [k for k in range(n) if lo_ <= mx[k] < hi_]
    acc = sum(m >= hi_ for m in mx)
    nn = 1500
    fa = sum(E4[str(k)] is not None for k in range(nn) if lo_ <= mx[k] < hi_) + sum(mx[k] >= hi_ for k in range(nn))
    out.append(f'| {tag} | {lo_}/{hi_} | {len(routed) / n:.1%} | {acc} | {fa}/{nn} = {fa / nn:.2%} |')
# 고정 문턱 lo 0.10 / hi 0.6 에서도(보조)
out += ['', '## 보조: 같은 고정 문턱 lo 0.10 / hi 0.6 (선택 없음)', '| 앞단 | 303문제 정답 | 넘김 호출(303) | 잡담 LLM 넘김 | 잡담 오답 비율(앞 1,500) |', '|---|---:|---:|---:|---:|']
for tag, suf in (('e16c', ''), ('e16d', '_e16d')):
    ns = res[tag]['ns']
    run, SETS = ns['run'], res[tag]['SETS']
    ok = calls = 0
    for w in ('mix6', 'mix7'):
        for i, x in enumerate(SETS[w]['qs']):
            p, u = run(w, i, 0.10, 0.6, M)
            ok += p == x['gold']
            calls += u
    fr = J(R(f'chat_front_mix7{suf}.json'))
    mx = [max(r) for r in fr['sims']]
    routed = sum(0.10 <= m < 0.6 for m in mx) / len(mx)
    fa = sum(E4[str(k)] is not None for k in range(1500) if 0.10 <= mx[k] < 0.6) + sum(mx[k] >= 0.6 for k in range(1500))
    out.append(f'| {tag} | {ok} | {calls}/303 | {routed:.1%} | {fa / 1500:.2%} |')
print('\n'.join(out))
if '--md' in sys.argv:
    open(sys.argv[sys.argv.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
