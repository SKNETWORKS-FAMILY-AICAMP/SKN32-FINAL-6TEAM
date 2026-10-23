# 「한 줄로 이은 시험」(server/chain_e2e.py) 결과를 문서용 표로 만든다. 입력: results/_pull/chain/chain_*.json(문제별 추적) · chain_summary.json.
# 사용: python chain_report.py > results/chain_report.txt
import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
D = os.path.join(HERE, 'results', '_pull', 'chain')
sys.stdout.reconfigure(encoding='utf-8')
summ = json.load(open(os.path.join(D, 'chain_summary.json'), encoding='utf-8'))
TR = {os.path.basename(f)[6:-5]: json.load(open(f, encoding='utf-8')) for f in glob.glob(os.path.join(D, 'chain_*.json')) if not f.endswith('summary.json')}
LAB = {'e4b_only': '단독 기준선: 가르친 E4B 만(같은 서버·같은 GGUF)', 'full': '한 줄 연결 — 수정 판(Jev 계열 모델 Winnow-E4B[학습 없음] 입력에 고객 일정 목록)', 'full_v1': '한 줄 연결 — 사전 등록 판(Jev 계열 모델 입력에 「일정 보유」 한 줄만)',
       'full_noctx': '한 줄 연결 — Jev 계열 모델 입력에 메시지만', 'no_rules': '수정 판에서 규칙 뺌', 'no_jev': '수정 판에서 Jev 계열 모델 뺌(ML 이 범위 밖만 거름)', 'no_ml': '수정 판에서 ML 판별기 뺌', 'rules_e4b': '규칙 → E4B(ML·Jev 모두 뺌)',
       'full_live': '(수정 판 다시 호출 — 캐시 없음)', 'e4b_only_live': '(단독 기준선 다시 호출 — 캐시 없음)'}
ORDER = ['e4b_only', 'rules_e4b', 'no_jev', 'no_ml', 'no_rules', 'full', 'full_v1', 'full_noctx']
key = lambda n: n.replace('#', '_')
GS = json.load(open(fixture('gold_sets.json'), encoding='utf-8'))


def rf(x):
    """전문가가 답을 읽지 못한(빈 응답) 문제 — 정답이 「없음」인 문제에서 빈 응답이 우연히 맞게 세어지는 것을 막으려고 틀린 것으로 센다(§86 과 같은 규칙)."""
    return any(f.startswith('parse_fail') for f in x['fail'])


def okk(x):
    return x['pick'] == x['gold'] and not rf(x)


def strict(traces):
    import math
    r = collections.Counter()
    lat = sorted(x['total_ms'] for x in traces)
    calls = collections.Counter()
    for x in traces:
        for k, v in x['calls'].items():
            calls[k] += v
        if x['type'] == 'compound_intent':
            r['comp_A'] += (x['pick'] == x['gold'] and not rf(x))
            r['comp_B'] += (x['pick'] in (GS[x['set']].get(str(x['qi'])) or []) and not rf(x))
            continue
        r['n'] += 1
        o = okk(x)
        r['ok'] += o
        r['read_fail'] += rf(x)
        r['wrong'] += (x['pick'] is not None and x['pick'] != x['gold'])
        r['miss'] += (x['pick'] is None and x['gold'] is not None and not rf(x))
    r['lat_med'], r['lat_p95'] = lat[len(lat) // 2], lat[int(len(lat) * 0.95)]
    r['calls'] = dict(calls)
    return r


def mcn(a, b):
    import math
    x = y = 0
    for ta, tb in zip(a, b):
        if ta['type'] == 'compound_intent':
            continue
        oa, ob = okk(ta), okk(tb)
        x += oa and not ob
        y += ob and not oa
    n = x + y
    return x, y, (1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(x, y) + 1)) / 2 ** n))


ST = {n: strict(t) for n, t in TR.items()}

print('### 변형별 결과 — 요청 둘 제외 769문제(mix8~12), 가르친 E4B 단독과 짝지은 정확검정 (★빈 응답은 틀린 것으로 센다)')
print('| 변형 | 정답/769 | 엉뚱한 답 | 못 찾음 | 읽기 실패 | 요청 둘 A · B (/66) | 호출: 규칙·ML·Jev 계열 모델·E4B | 건당 중앙 · p95(ms) | 단독 대비(이쪽만 : 단독만, p) |')
print('|---|---:|---:|---:|---:|---|---|---|---|')
for n in ORDER:
    r = ST.get(n)
    if not r:
        continue
    c = r['calls']
    vs = mcn(TR[n], TR['e4b_only']) if n != 'e4b_only' else None
    print(f"| {LAB[n]} | **{r['ok']}** ({100 * r['ok'] / r['n']:.1f}%) | {r['wrong']} | {r['miss']} | {r['read_fail']} | {r['comp_A']} · {r['comp_B']} | {c.get('rules', 0)} · {c.get('ml', 0)} · {c.get('jev', 0)} · {c.get('e4b', 0)} | {r['lat_med']:.0f} · {r['lat_p95']:.0f} | "
          + (f'{vs[0]} : {vs[1]} (p={vs[2]:.3g})' if vs else '—') + ' |')
print()
print('### 실제 지연(캐시 없이 다시 호출한 판 — 단계 시간의 합)')
for n in ('e4b_only#live', 'full#live'):
    r = summ.get(n)
    if r:
        st = ST[key(n)]
        print(f"- {LAB[key(n)]}: 건당 중앙 {st['lat_med']:.0f}ms · p95 {st['lat_p95']:.0f}ms · 첫 판과 같은 답 {r.get('same_pick_as_first_pass')} · 엄격 정답 {st['ok']}/769")
print()
for n in ('full', 'full_v1'):
    t = TR.get(n)
    if not t:
        continue
    print(f'### {LAB[n]} — 단계별로 어디서 끝났나(835문제)')
    ended = collections.Counter(x['ended'] for x in t)
    print('- ' + ' · '.join(f'{k} {v}' for k, v in ended.most_common()))
    byby = collections.Counter(x.get('route_by') for x in t if x['ended'] != 'rules')
    print('- 보낼 곳을 정한 쪽: ' + ' · '.join(f'{k} {v}' for k, v in byby.most_common()))
    r = summ[n]['routing']
    print('- 선택(정답 경로 → 고른 경로): ' + ' · '.join(f'{k} {v}' for k, v in sorted(r[0].items())))
    cc = collections.Counter()
    for x in t:
        if x['route'] is None or x.get('route_by') in (None, 'default') or x['ended'] == 'rules':
            continue
        cc[(x['route_gold'] == x['route'], okk(x))] += 1
    print('- 선택이 맞았을 때와 틀렸을 때의 최종 결과(빈 응답은 틀림): ' + ' · '.join(f"경로{'맞음' if a else '틀림'}·최종{'정답' if b else '오답'} {v}" for (a, b), v in sorted(cc.items())))
    tot = sum(r[0].values())
    ok = r[0].get('point→point', 0) + r[0].get('reject→reject', 0)
    fr = r[0].get('point→reject', 0)
    fp = r[0].get('reject→point', 0)
    print(f'- 선택 정확도 {ok}/{tot} = {100 * ok / tot:.1f}% · 일정 질문을 범위 밖으로 잘못 닫음 {fr}/{r[0].get("point→reject", 0) + r[0].get("point→point", 0)} · 잡담을 짚기로 잘못 보냄 {fp}/{r[0].get("reject→reject", 0) + r[0].get("reject→point", 0)}')
    fails = collections.Counter(f.split(':')[0] for x in t for f in x['fail'])
    print('- 실패 사유: ' + (' · '.join(f'{k} {v}' for k, v in fails.items()) if fails else '없음'))
    print()
print('### 유형별 정답(요청 둘 제외, 엄격) — 단독 대비 어디서 잃나')
head = [n for n in ('e4b_only', 'rules_e4b', 'no_jev', 'full', 'full_v1') if n in TR]
types = sorted({x['type'] for x in TR['e4b_only'] if x['type'] != 'compound_intent'})
print('| 유형 | ' + ' | '.join(head) + ' |')
print('|---|' + '---:|' * len(head))
for t in types:
    row = []
    for n in head:
        xs = [x for x in TR[n] if x['type'] == t]
        row.append(f"{sum(okk(x) for x in xs)}/{len(xs)}")
    print(f'| {t} | ' + ' | '.join(row) + ' |')
