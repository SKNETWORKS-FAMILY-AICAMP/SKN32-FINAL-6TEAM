# 거부권 검토자에게 줄 「짧은 확인 질문」 입력을 만든다 — 일정 전체를 다시 읽히지 않고 (고객 말 + 짚기 모델이 고른 일정 항목 한 줄)만 보여 준다(사용자 제안 ⓐ의 구현: 독립 검토자가 고른 항목이 맞는지 확인).
#  대상: 가르친 E4B 시드 1·2·3(서비스 기반 Q4_K_M)이 D · D2 · D3 에서 「항목을 골랐던」 모든 답(중복 제거). 검토자: FrogNano · 가르치기 전 E4B · (필요하면 Codex 솔).
# 사용: [VERIFY_EXTRA_TAGS=oos1,oos2] python build_verify_inputs.py <출력 verify_inputs.json>
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'results', 'd_test')
E = os.path.join(HERE, 'results', 'empty_probe')
sys.stdout.reconfigure(encoding='utf-8')
dst = sys.argv[1]
SETS = {'D': ('all_prompts.json', 'd_test_lp_{}.jsonl', {'e4bt': 'q4km_e4bt', 'e4bs2': 'q4km_e4bs2', 'e4bs3': 'q4km_e4bs3'}),
        'D2': ('all_prompts_d2.json', 'd_test_lp_d2_{}.jsonl', {'e4bt': 'q4km_e4bt', 'e4bs2': 'q4km_e4bs2', 'e4bs3': 'q4km_e4bs3'}),
        'D3': ('all_prompts_d3.json', 'd_test_d3_{}.jsonl', {'e4bt': 'q4km_e4bt', 'e4bs2': 'q4km_e4bs2', 'e4bs3': 'q4km_e4bs3'})}
# 잡담 부정 사례를 더해 다시 가르친 짚기 모델(oos1·oos2·oos3)의 답도 같은 검토를 받게 한다 — 결과 파일이 있는 것만 더한다.
for tag in [t for t in os.environ.get('VERIFY_EXTRA_TAGS', '').split(',') if t]:
    for ds, (pf, ff, tags) in SETS.items():
        if os.path.exists(os.path.join(D, ff.format('q4km_' + tag))):
            tags[tag] = 'q4km_' + tag
QRE = re.compile(r'고객 질문: (.*?)\n\n', re.S)
items, seen = [], set()
for ds, (pf, ff, tags) in SETS.items():
    P = {p['i']: p for p in json.load(open(os.path.join(E, pf), encoding='utf-8'))}
    for seed, tag in tags.items():
        for line in open(os.path.join(D, ff.format(tag)), encoding='utf-8'):
            r = json.loads(line)
            if r.get('pick') is None or r['i'] not in P:
                continue
            key = f"{ds}|{r['i']}|{r['pick']}"
            if key in seen:
                continue
            seen.add(key)
            pr = P[r['i']]['prompt']
            q = QRE.search(pr).group(1).strip()
            m = re.search(rf'^{r["pick"]}\. (.*)$', pr, re.M)
            if not m:
                continue
            items.append({'key': key, 'ds': ds, 'i': r['i'], 'pick': r['pick'], 'q': q, 'line': m.group(1).strip()})
json.dump(items, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
print(len(items), '건', {ds: sum(1 for x in items if x['ds'] == ds) for ds in SETS})
