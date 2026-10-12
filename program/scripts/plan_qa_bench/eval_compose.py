# 파트별 합성 측정 — 규칙 분기: 문장에서 날·순서·앞뒤 표현이 읽혀 코드가 항목을 확정하면(S2) 그 답을 쓰고, 아니면 「기본 짚기 모델」 답을 쓴다.
#  기본 짚기 모델 = Gemma E4B / 12B / 26B / Jev(규칙 후보 줄임). 기준 항목은 Jev 가 짚는다(jev_slots_heavy.json).
#  판정 = heavy held 88문항. 유형을 미리 알려 주지 않는다(분기는 규칙이 읽은 자리표뿐). 규칙은 ord2 오류를 보고 고쳤고 heavy 문장 표현은 알고 있었다 `[주의]`.
# 사용: python eval_compose.py
import json, os
from collections import defaultdict
from slot_lookup import resolve
from rule_slots import rule_slots

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda f: os.path.join(HERE, 'results', f)
J = lambda f: json.load(open(f, encoding='utf-8'))
st = J(os.path.join(HERE, 'fixtures', 'heavy.json'))['sets']['heavy']
qs, items = st['qs'], st['items']
g = J(R('llm_heavy_out.json'))
jrows = J(R('jev_slots_heavy.json'))['heavy']
jr = J(R('jev_out_heavy_rules.json'))['heavy']['rows']


def jev_rules(i):
    p = jr[i]['probs']; k = max(p, key=p.get)
    return None if k == 'none' else int(k.split('_')[1])


BASES = {'E4B': lambda i: g['gemma4:e4b']['picks'][i], '12B': lambda i: g['gemma4:12b']['picks'][i],
         '26B': lambda i: g['gemma4:26b']['picks'][i], 'Jev(규칙)': jev_rules}
held = [i for i, x in enumerate(qs) if x['split'] == 'held']


def s2(i):
    rs = rule_slots(qs[i]['q'], items)
    sl = {'anchor': jrows[i]['slots'].get('anchor'), 'nextday': rs['nextday'], 'kw': rs['kw']}
    for k in ('day', 'pos', 'kind', 'meal', 'rel'):
        sl[k] = rs[k]
    return resolve(items, sl)


routed = {i: s2(i) for i in range(len(qs))}
used = [i for i in held if routed[i][0] in ('item', 'none')]
print(f"S2 가 확정한 판정 문제 {len(used)}/88 — 유형 분포:", dict(sorted(((t, sum(qs[i]['type'] == t for i in used)) for t in {qs[i]['type'] for i in used}), key=lambda a: -a[1])))
print(f"  그중 정답 맞음 {sum((routed[i][1] if routed[i][0] == 'item' else None) == qs[i]['gold'] for i in used)}/{len(used)}")


def comp(base):
    def f(i):
        r = routed[i]
        return r[1] if r[0] == 'item' else (None if r[0] == 'none' else base(i))
    return f


def stat(get):
    ok = bad = miss = 0
    bt = defaultdict(int)
    for i in held:
        p, gd = get(i), qs[i]['gold']
        ok += (p == gd); bad += (p is not None and p != gd); miss += (p is None and gd is not None)
        bt[qs[i]['type']] += (p == gd)
    return ok, bad, miss, bt


print('\n판정 88문항 (각 1회)')
res = {}
for n, b in BASES.items():
    a = stat(b); c = stat(comp(b))
    res[n] = (a, c)
    print(f"  {n:<10} 단독 {a[0]}/88={a[0] / 88:.0%} 엉뚱 {a[1]} 못 찾음 {a[2]}  →  + 규칙·조회 분기 {c[0]}/88={c[0] / 88:.0%} 엉뚱 {c[1]} 못 찾음 {c[2]}")
print('\n유형별 (분기 후, 유형당 8)')
types = list(dict.fromkeys(x['type'] for x in qs))
print('  ' + '유형'.ljust(22) + ' '.join(n.ljust(10) for n in BASES))
for t in types:
    print('  ' + t.ljust(22) + ' '.join(f"{res[n][1][3][t]}/8".ljust(10) for n in BASES))
# 분기가 원래 맞던 문제를 망친 경우
for n, b in BASES.items():
    broke = [i for i in held if b(i) == qs[i]['gold'] and comp(b)(i) != qs[i]['gold']]
    if broke:
        print(f"\n[{n}] 분기가 맞던 답을 틀리게 한 문제 {len(broke)}개:", '; '.join(qs[i]['q'] for i in broke[:6]))
