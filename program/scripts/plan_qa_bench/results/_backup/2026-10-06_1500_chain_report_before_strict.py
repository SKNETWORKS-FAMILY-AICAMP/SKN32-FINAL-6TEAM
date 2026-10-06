# 「한 줄로 이은 시험」(server/chain_e2e.py) 결과를 문서용 표로 만든다. 입력: results/_pull/chain/chain_*.json(문제별 추적) · chain_summary.json.
# 사용: python chain_report.py > results/chain_report.txt
import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'results', '_pull', 'chain')
sys.stdout.reconfigure(encoding='utf-8')
summ = json.load(open(os.path.join(D, 'chain_summary.json'), encoding='utf-8'))
TR = {os.path.basename(f)[6:-5]: json.load(open(f, encoding='utf-8')) for f in glob.glob(os.path.join(D, 'chain_*.json')) if not f.endswith('summary.json')}
LAB = {'e4b_only': '단독 기준선: 가르친 E4B 만(같은 서버·같은 GGUF)', 'full': '한 줄 연결 — 수정 판(Jev 입력에 고객 일정 목록)', 'full_v1': '한 줄 연결 — 사전 등록 판(Jev 입력에 「일정 보유」 한 줄만)',
       'full_noctx': '한 줄 연결 — Jev 입력에 메시지만', 'no_rules': '수정 판에서 규칙 뺌', 'no_jev': '수정 판에서 Jev 뺌(ML 이 범위 밖만 거름)', 'no_ml': '수정 판에서 ML 판별기 뺌', 'rules_e4b': '규칙 → E4B(ML·Jev 모두 뺌)',
       'full_live': '(수정 판 다시 호출 — 캐시 없음)', 'e4b_only_live': '(단독 기준선 다시 호출 — 캐시 없음)'}
ORDER = ['e4b_only', 'rules_e4b', 'no_jev', 'no_ml', 'no_rules', 'full', 'full_v1', 'full_noctx']
key = lambda n: n.replace('#', '_')

print('### 변형별 결과 — 요청 둘 제외 769문제(mix8~12), 가르친 E4B 단독과 짝지은 정확검정')
print('| 변형 | 정답/769 | 엉뚱한 답 | 못 찾음 | 요청 둘 A · B (/66) | 호출: 규칙·ML·Jev·E4B | 건당 중앙 · p95(ms) | 단독 대비(이쪽만 : 단독만, p) |')
print('|---|---:|---:|---:|---|---|---|---|')
for n in ORDER:
    r = summ.get(n)
    if not r:
        continue
    c = r['calls']
    vs = r.get('vs_e4b_only(a만,b만,p)')
    print(f"| {LAB[n]} | **{r['ok769']}** ({100 * r['ok769'] / r['n769']:.1f}%) | {r['wrong769']} | {r['miss769']} | {r['comp_A']} · {r['comp_B']} | {c.get('rules', 0)} · {c.get('ml', 0)} · {c.get('jev', 0)} · {c.get('e4b', 0)} | {r['lat_median_ms']:.0f} · {r['lat_p95_ms']:.0f} | "
          + (f'{vs[0]} : {vs[1]} (p={vs[2]:.3g})' if vs else '—') + ' |')
print()
print('### 실제 지연(캐시 없이 다시 호출한 판 — 단계 시간의 합)')
for n in ('e4b_only#live', 'full#live'):
    r = summ.get(n)
    if r:
        print(f"- {LAB[key(n)]}: 건당 중앙 {r['lat_median_ms']:.0f}ms · p95 {r['lat_p95_ms']:.0f}ms · 첫 판과 같은 답 {r.get('same_pick_as_first_pass')}")
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
    print('- 선택이 맞았을 때와 틀렸을 때의 최종 결과: ' + ' · '.join(f'{k} {v}' for k, v in sorted(r[1].items())))
    tot = sum(r[0].values())
    ok = r[0].get('point→point', 0) + r[0].get('reject→reject', 0)
    fr = r[0].get('point→reject', 0)
    fp = r[0].get('reject→point', 0)
    print(f'- 선택 정확도 {ok}/{tot} = {100 * ok / tot:.1f}% · 일정 질문을 범위 밖으로 잘못 닫음 {fr}/{r[0].get("point→reject", 0) + r[0].get("point→point", 0)} · 잡담을 짚기로 잘못 보냄 {fp}/{r[0].get("reject→reject", 0) + r[0].get("reject→point", 0)}')
    fails = collections.Counter(f.split(':')[0] for x in t for f in x['fail'])
    print('- 실패 사유: ' + (' · '.join(f'{k} {v}' for k, v in fails.items()) if fails else '없음'))
    print()
print('### 유형별 정답(요청 둘 제외) — 단독 대비 어디서 잃나')
base = summ['e4b_only']['by_type']
head = ['e4b_only'] + [n for n in ('full', 'full_v1', 'no_jev') if n in summ]
print('| 유형 | ' + ' | '.join(n for n in head) + ' |')
print('|---|' + '---:|' * len(head))
for t in sorted(base):
    print(f'| {t} | ' + ' | '.join(f"{summ[n]['by_type'][t][0]}/{summ[n]['by_type'][t][1]}" for n in head) + ' |')
