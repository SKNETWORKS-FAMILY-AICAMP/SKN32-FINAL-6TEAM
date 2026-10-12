# Claude 하위 작업이 쓴 답(out_<모델>_<세트>.json)을 원래 문제 번호로 되돌려 채점하고 results/ 에 원본을 둔다.
# 사용: python claude_batch_collect.py <배치 폴더> <모델 짧은이름(fable|opus)> <세트들,쉼표> [--merge]
#   --merge : results/llm_<세트>_out.json 에 키 'claude-<모델>-묶음' 으로 짚은 답을 덧붙인다(덮어쓰기 전 백업).
import json, os, shutil, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BD, TAG, SETS = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
MERGE = '--merge' in sys.argv
KEY = {'fable': 'claude-fable-5.1-묶음', 'opus': 'claude-opus-5.5-묶음'}[TAG]
CAVEAT = '세트 전체를 한 번에 푼 묶음 풀이 + 생각 설정 통제 불가(켜져 있었을 수 있음). 로컬(문제 하나씩·생각 끔)과 공정한 비교가 아님 — 천장 참고용(§62·§62-2)'
tot_ok = tot_n = 0
bytype = defaultdict(lambda: [0, 0])
for name in SETS:
    f = os.path.join(BD, f'out_{TAG}_{name}.json')
    if not os.path.exists(f):
        print(name, '결과 파일 없음')
        continue
    ans = json.load(open(f, encoding='utf-8'))['answers']
    perm = json.load(open(os.path.join(BD, f'perm_{name}.json')))
    job = json.load(open(os.path.join(HERE, 'fixtures', f'{name}.json'), encoding='utf-8'))['sets'][name]
    ids = {i['id'] for i in job['items']}
    n = len(job['qs'])
    picks = [None] * n
    miss = 0
    for pos, k in enumerate(perm):
        if str(pos) not in ans:
            miss += 1
            continue
        v = ans[str(pos)]
        picks[k] = v if v in ids else None
    ok = sum(int(picks[k] == job['qs'][k]['gold']) for k in range(n))
    wrong = [k for k in range(n) if picks[k] != job['qs'][k]['gold']]
    tot_ok += ok
    tot_n += n
    for k in range(n):
        t = job['qs'][k]['type']
        bytype[t][1] += 1
        bytype[t][0] += int(picks[k] == job['qs'][k]['gold'])
    nn = sum(1 for k in range(n) if picks[k] is None and job['qs'][k]['gold'] is not None)
    print(f'{TAG} {name}: {ok}/{n} = {100 * ok / n:.1f}%  (답 누락 {miss} · 일정 문제를 null 로 답함 {nn} · 엉뚱한 번호 {len(wrong) - nn - sum(1 for k in range(n) if picks[k] is not None and job["qs"][k]["gold"] is None)} · 없는 문제에 번호를 댐 {sum(1 for k in range(n) if picks[k] is not None and job["qs"][k]["gold"] is None)})')
    json.dump({'model': KEY, 'set': name, 'picks': picks, 'wrong': wrong, 'source': os.path.basename(f), 'n_answers': len(ans), 'fair_comparison': False, 'caveat': CAVEAT, 'condition': {'solving': 'set-bundled', 'thinking': 'uncontrolled(subagent default)', 'question_order': 'shuffled(seed 20261004)'}},
              open(os.path.join(HERE, 'results', f'claude_batch_{TAG}_{name}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    if MERGE:
        of = os.path.join(HERE, 'results', f'llm_{name}_out.json')
        o = json.load(open(of, encoding='utf-8')) if os.path.exists(of) else {}
        bk = os.path.join(HERE, 'results', '_backup', '2026-10-04_claude_batch_merge')
        os.makedirs(bk, exist_ok=True)
        if os.path.exists(of) and not os.path.exists(os.path.join(bk, os.path.basename(of))):
            shutil.copy(of, os.path.join(bk, os.path.basename(of)))
        o[KEY] = {'picks': picks, '_sec_per_q': None, '_errors': miss, '_fair_comparison': False, '_caveat': CAVEAT}
        json.dump(o, open(of, 'w', encoding='utf-8'), ensure_ascii=False)
print(f'합계 {tot_ok}/{tot_n} = {100 * tot_ok / max(1, tot_n):.1f}%')
print('유형별', {t: f'{a}/{b}' for t, (a, b) in bytype.items()})
