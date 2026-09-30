# 작은 모델 전문가 구조(Jev·26B·투표 없음) 채점.
#  흐름: ①절 분석(clauses) → ②규칙 자리표(rule_slots) + 조회 코드(slot_lookup)로 확정되면 그 답 (기준 항목이 필요하면 anchor 전문가를 부른다)
#        → ③확정 못 하면 gate 전문가(일정 관련 여부)가 false 면 「없음」 → ④point 전문가가 대상 절이 가리키는 항목을 짚고 → ⑤같은 모델이 verify(짚은 항목이 문장과 정말 맞는지) 로 거른다.
#  세 역할(gate·anchor·point)에 E4B/12B 중 누구를 쓸지는 「개발용(dev) 문제」의 정확도로만 고르고, 판정 문제(held)는 그 뒤 한 번만 본다.
# 사용: python eval_pipeline.py <job> [--pick-on <dev를 가진 job>]     (기본: heavy)
import itertools, json, os, sys
from collections import defaultdict
from clauses import analyze
from rule_slots import rule_slots
from slot_lookup import resolve

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda f: os.path.join(HERE, 'results', f)
J = lambda f: json.load(open(f, encoding='utf-8'))
MODELS = ['gemma4:e4b', 'gemma4:12b']


def load(job):
    st = J(os.path.join(HERE, 'fixtures', f'{job}.json'))['sets'][job]
    return st['qs'], st['items'], J(R(f'llm_tasks_out_{job}.json'))


def run_one(i, cfg, qs, items, out):
    q = qs[i]['q']
    a = analyze(q)
    tt = a['tt']
    rs = rule_slots(tt, items)
    if rs['day'] is None:
        rs['day'] = rule_slots(q, items)['day']
    calls = []
    anchor = None
    if rs['rel'] is not None:
        calls.append(('anchor', cfg[1]))
        anchor = out[cfg[1]]['anchor_excl'][i] if a['negation'] else out[cfg[1]]['anchor_tt'][i]
    slots = {k: rs[k] for k in ('day', 'pos', 'kind', 'meal', 'rel', 'kw', 'nextday')}
    slots['anchor'] = anchor
    r = resolve(items, slots)
    if r[0] == 'item':
        return r[1], calls, 'struct'
    if r[0] == 'none':
        return None, calls, 'struct'
    calls.append(('gate', cfg[0]))
    if not out[cfg[0]]['gate2'][i]:
        return None, calls, 'gate'
    calls.append(('point', cfg[2]))
    p = out[cfg[2]]['point'][i]
    if p is not None:                       # 짚은 항목이 문장과 정말 맞는지 같은 모델이 한 번 더 확인(verify)
        calls.append(('verify', cfg[2]))
        if out[cfg[2]]['verify'][i] is False:
            return None, calls, 'verify'
    return p, calls, 'point'


def evaluate(cfg, qs, items, out, idx):
    ok = bad = miss = 0
    bt = defaultdict(int)
    sec = 0.0
    src = defaultdict(int)
    for i in idx:
        p, calls, how = run_one(i, cfg, qs, items, out)
        g = qs[i]['gold']
        ok += (p == g); bad += (p is not None and p != g); miss += (p is None and g is not None)
        bt[qs[i]['type']] += (p == g)
        sec += sum(out[m]['sec_per_q'] / 4 for _, m in calls)
        src[how] += 1
    return ok, bad, miss, bt, sec / len(idx), dict(src)


if __name__ == '__main__':
    job = sys.argv[1] if len(sys.argv) > 1 else 'heavy'
    qs, items, out = load(job)
    dev = [i for i, x in enumerate(qs) if x.get('split') == 'dev']
    held = [i for i, x in enumerate(qs) if x.get('split') == 'held']
    cfgs = list(itertools.product(MODELS, repeat=3))
    print(f'## {job} — dev {len(dev)} · held {len(held)}   (역할 순서: gate · anchor · point)')
    rows = []
    for cfg in cfgs:
        d = evaluate(cfg, qs, items, out, dev)
        h = evaluate(cfg, qs, items, out, held)
        rows.append((cfg, d, h))
        print(f"  {'/'.join(m.split(':')[1] for m in cfg):<14} dev {d[0]}/{len(dev)} · held {h[0]}/{len(held)}={h[0] / len(held):.0%} 엉뚱 {h[1]} 못 찾음 {h[2]} · 평균 약 {h[4]:.1f}초/질문(추정) · 처리 {h[5]}")
    best = max(rows, key=lambda r: (r[1][0], -r[1][1], -sum(m == 'gemma4:12b' for m in r[0])))
    print('\n개발용 정확도로 고른 배치:', '/'.join(m.split(':')[1] for m in best[0]), f"→ 판정 {best[2][0]}/{len(held)}")
    types = list(dict.fromkeys(x['type'] for x in qs))
    per = defaultdict(int)
    for t in types:
        n = sum(1 for i in held if qs[i]['type'] == t)
        print(f"  {t:<22} {best[2][3][t]}/{n}")
