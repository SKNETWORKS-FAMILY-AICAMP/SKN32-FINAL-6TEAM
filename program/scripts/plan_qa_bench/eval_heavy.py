# 무거운 세트(heavy.json)와 기존 세트(job.json) 결과를 한 표로 채점한다. 판정 = held(88) / 보류 90, 문턱은 dev 에서만 고른다.
#  · Jev(jev_out_*.json): 선택지별 확률의 최고값이 답, 「none」이거나 최고 확률이 문턱 미만이면 「못 찾음」
#  · Codex(codex_*.json), Gemma(llm_out.json · llm_heavy_out.json)
# 채점: 엉뚱한 답 = 틀린 항목 + 없는 질문에 항목 / 못 찾음 = 정답이 있는데 null. 사용: python eval_heavy.py
import json, os
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda f: os.path.join(HERE, 'results', f)
J = lambda f: json.load(open(f, encoding='utf-8'))
job = J(os.path.join(HERE, 'fixtures', 'job.json'))['sets']
heavy = J(os.path.join(HERE, 'fixtures', 'heavy.json'))['sets']['heavy']['qs']


def jev_pick(res, s, qi, tau):
    pr = res[s]['rows'][qi]['probs']
    k = max(pr, key=pr.get)
    if k == 'none' or pr[k] < tau:
        return None
    return int(k.split('_')[1])


def best_tau(get, dev):
    def sc(t):
        ok = bad = 0
        for g, p in ((g, get(t, i)) for g, i in dev):
            ok += (p == g); bad += (p is not None and p != g)
        return ok - 2 * bad
    return max([x / 20 for x in range(20)], key=sc)


def stat(pairs):
    ok = sum(p == g for g, p in pairs)
    bad = sum(p is not None and p != g for g, p in pairs)
    miss = sum(p is None and g is not None for g, p in pairs)
    return ok, len(pairs), bad, miss


def fmt(name, a, extra=''):
    print(f"  {name:<34} {a[0]}/{a[1]}={a[0] / a[1]:.0%} 엉뚱 {a[2]} 못 찾음 {a[3]} {extra}")


print('## A. 기존 보류 90문항(test50+hard40) — Jev 를 Gemma·Codex 와 같은 문제로 비교')
DEV, HELD = ('mine38', 'dev50'), ('test50', 'hard40')
gem = J(R('llm_out.json'))
for m in ('gemma4:e4b', 'gemma4:12b', 'gemma4:26b'):
    fmt(m, stat([(x['gold'], gem[m][s][qi]) for s in HELD for qi, x in enumerate(job[s]['qs'])]))
for tag in ('gpt-6-luna', 'gpt-6-sol'):
    c = J(R(f'codex_{tag}.json'))
    fmt(tag, stat([(x['gold'], c[s].get(str(qi))) for s in HELD for qi, x in enumerate(job[s]['qs'])]))
for f, name in (('jev_out_job.json', 'Jev(전체 후보)'), ('jev_out_job_rules.json', 'Jev(규칙으로 후보 줄임)')):
    if not os.path.exists(R(f)):
        continue
    res = J(R(f))
    devp = [(job[s]['qs'][qi]['gold'], (s, qi)) for s in DEV for qi in range(len(job[s]['qs']))]
    tau = best_tau(lambda t, sq: jev_pick(res, sq[0], sq[1], t), [(g, sq) for g, sq in devp])
    for label, t in (('문턱 없음', 0.0), (f'문턱 {tau:.2f}', tau)):
        fmt(f'{name} · {label}', stat([(x['gold'], jev_pick(res, s, qi, t)) for s in HELD for qi, x in enumerate(job[s]['qs'])]), f"{res['_sec_per_q']:.2f}초/질문")

print('\n## B. 무거운 세트 held 88문항 (dev 44 는 문턱 고르기에만)')
hidx = [i for i, x in enumerate(heavy) if x['split'] == 'held']
didx = [i for i, x in enumerate(heavy) if x['split'] == 'dev']
methods = {}
if os.path.exists(R('llm_heavy_out.json')):
    gh = J(R('llm_heavy_out.json'))
    for k, v in gh.items():
        methods[k] = lambda i, v=v: v['picks'][i]
    for suffix in ('', '#nohist', '#pool', '#proto'):
        ks = [f'gemma4:{m}{suffix}' for m in ('e4b', '12b', '26b')]
        if all(k in gh for k in ks):
            methods[f'cascade(e4b·12b 합의→26b){suffix}'] = lambda i, ks=ks, gh=gh: (gh[ks[0]]['picks'][i] if gh[ks[0]]['picks'][i] == gh[ks[1]]['picks'][i] else gh[ks[2]]['picks'][i])
for tag in ('gpt-6-luna', 'gpt-6-sol'):
    for sf, lab in (('', ''), ('_proto', '#proto')):
        f = R(f'codex_{tag}_heavy{sf}.json')
        if os.path.exists(f):
            c = J(f)['heavy']
            methods[tag + lab] = lambda i, c=c: c.get(str(i))
for f, name in (('jev_out_heavy.json', 'Jev(전체 후보)'), ('jev_out_heavy_rules.json', 'Jev(규칙 후보 줄임)'),
                ('jev_out_heavy_proto.json', 'Jev(전체 후보)#proto'), ('jev_out_heavy_rules_proto.json', 'Jev(규칙 후보 줄임)#proto')):
    if os.path.exists(R(f)):
        res = J(R(f))
        for label, tau in (('문턱 없음', 0.0), ('dev 문턱', best_tau(lambda t, i: jev_pick(res, 'heavy', i, t), [(heavy[i]['gold'], i) for i in didx]))):
            methods[f'{name} · {label}'] = lambda i, res=res, tau=tau: jev_pick(res, 'heavy', i, tau)
tab = {}
for name, get in methods.items():
    a = stat([(heavy[i]['gold'], get(i)) for i in hidx])
    fmt(name, a)
    bt = defaultdict(list)
    for i in hidx:
        bt[heavy[i]['type']].append((heavy[i]['gold'], get(i)))
    tab[name] = {t: stat(v) for t, v in bt.items()}
types = list(dict.fromkeys(x['type'] for x in heavy))
print('\n## C. 유형별 맞은 개수 (held 유형당 8문제)')
names = list(methods)
for k, n in enumerate(names):
    print(f'  [{k + 1}] {n}')
print('  ' + '유형'.ljust(22) + ' '.join(f'[{k + 1}]'.ljust(10) for k in range(len(names))))
for t in types:
    print('  ' + t.ljust(22) + ' '.join((f'{tab[n][t][0]}/8(엉{tab[n][t][2]})').ljust(10) for n in names))
