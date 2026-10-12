# 서버 결과(llm_out.json · emb_rr_out.json)를 같은 기준으로 판정한다.
# 문턱은 개발용(mine38 + dev50)에서만 정하고, 판정은 보류 묶음(test50 + hard40)으로 한다.
import json, os, re, sys
from collections import defaultdict
from datetime import date

SP = sys.argv[1]
sys.path.insert(0, SP)
from recog_v2 import RecognizerV3, NEXT, PREV

J = SP + '/rerank_job/'
job = json.load(open(J + 'job.json', encoding='utf-8'))
cats = json.load(open(SP + '/kakao_cats.json', encoding='utf-8'))
REC = {}
for name, st in job['sets'].items():
    key = st['items'][0]['title']
    REC[name] = REC.get(key) or RecognizerV3(st['items'], cats, date.fromisoformat(st['today']), SP + '/alias_cache.json')
    REC[key] = REC[name]
DEV, HELD = ('mine38', 'dev50'), ('test50', 'hard40')


def gold(s):
    return [x['gold'] for x in job['sets'][s]['qs']]


def stats(s, out):
    g = gold(s)
    ok = sum(o == x for o, x in zip(out, g))
    wrong = sum(o is not None and x is not None and o != x for o, x in zip(out, g))
    fp = sum(o is not None and x is None for o, x in zip(out, g))
    miss = sum(o is None and x is not None for o, x in zip(out, g))
    return ok, wrong, fp, miss, len(g)


def consistent(s, q, pick):
    if pick is None or re.search(NEXT, q, re.I) or re.search(PREV, q, re.I):
        return True
    pool, sig = REC[s].filt(q)
    return (not sig) or pick in {i['id'] for i in pool}


def line(label, outs):
    tot = [0, 0, 0, 0, 0]
    parts = []
    for s in HELD:
        st = stats(s, outs[s])
        tot = [a + b for a, b in zip(tot, st)]
        parts.append(f"{s} {st[0]}/{st[4]}")
    bad = tot[1] + tot[2]
    return (f"| {label} | {' · '.join(parts)} | **{tot[0]}/{tot[4]} = {tot[0] / tot[4]:.0%}** | {bad} | {tot[3]} |", tot[0], bad)


rows = []
if os.path.exists(J + 'llm_out.json'):
    L = json.load(open(J + 'llm_out.json'))
    for m, res in L.items():
        if not all(s in res for s in HELD):
            continue
        raw = {s: res[s] for s in HELD}
        chk = {s: [p if consistent(s, x['q'], p) else None for p, x in zip(res[s], job['sets'][s]['qs'])] for s in HELD}
        sec = res.get('_sec_per_q', 0)
        rows.append(line(f"LLM {m} ({sec:.1f}초/질문)", raw))
        rows.append(line(f"LLM {m} + 규칙 되확인", chk))

if os.path.exists(J + 'emb_rr_out.json'):
    pairs = json.load(open(J + 'pairs.json', encoding='utf-8'))
    E = json.load(open(J + 'emb_rr_out.json'))
    for m, sc in E.items():
        T = defaultdict(dict)
        for p, s in zip(pairs, sc):
            T[(p['set'], p['qi'])][p['item']] = s

        def run(s, tau, rules):
            out = []
            for qi, x in enumerate(job['sets'][s]['qs']):
                d = T[(s, qi)]
                if rules:
                    pool, sig = REC[s].filt(x['q'])
                    ids = {i['id'] for i in pool}
                    if sig and not ids:
                        out.append(None)
                        continue
                    d = {k: v for k, v in d.items() if (k in ids or not sig)}
                top = max(d, key=d.get)
                out.append(top if d[top] >= tau else None)
            return out

        vals = sorted({round(v, 4) for v in sc})
        grid = [vals[int(i * (len(vals) - 1) / 200)] for i in range(201)]
        for rules in (False, True):
            best = max(grid, key=lambda t: sum((lambda st: st[0] - 2 * (st[1] + st[2]))(stats(s, run(s, t, rules))) for s in DEV))
            rows.append(line(f"{'임베딩' if 'Reranker' not in m and 'reranker' not in m else '재평가'} {m}{' + 규칙' if rules else ''} (문턱 {best:.4g})",
                             {s: run(s, best, rules) for s in HELD}))

print('| 방식 | 보류 묶음 | 합계 | 엉뚱한 답(틀린 항목+없는 질문 짚음) | 못 찾음 |')
print('|---|---|---|---|---|')
for r, ok, bad in sorted(rows, key=lambda r: (-r[1], r[2])):
    print(r)
