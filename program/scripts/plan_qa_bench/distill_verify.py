# 증류 파일럿 학습 자료 독립 검증 — 문제를 만든 쪽과 따로 푼 Claude 풀이(out_distill_pXX.json)를 정답과 비교한다.
#  풀이는 정답·유형 없이, 문제 순서를 섞은 과제 파일(claude_batch_tasks.py)로 받았다. perm_<세트>.json: 섞은 번호 n → 원래 번호 perm[n].
#  일치 기준: 일반 문제는 pick == gold, 요청 둘(gold_set 있음)은 pick ∈ gold_set. 불일치 문제는 어느 유형인지와 함께 남긴다.
# 사용: python distill_verify.py <풀이 폴더> p01 p02 ...   → results/distill_verify_report.json · fixtures/distill/verify_<pid>.json(불일치 원래 번호 목록)
import json, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SOLVE = sys.argv[1]
PIDS = sys.argv[2:]
report, by_type_tot, by_type_ok = {}, Counter(), Counter()
for pid in PIDS:
    name = f'distill_{pid}'
    job = json.load(open(os.path.join(HERE, 'fixtures', 'distill', f'{name}.json'), encoding='utf-8'))['sets'][name]
    perm = json.load(open(os.path.join(SOLVE, f'perm_{name}.json')))
    ans = json.load(open(os.path.join(SOLVE, f'out_{name}.json'), encoding='utf-8'))['answers']
    miss = [n for n in range(len(perm)) if str(n) not in ans]
    bad = []
    for n, k in enumerate(perm):
        if str(n) not in ans:
            continue
        x = job['qs'][k]
        pick = ans[str(n)]
        ok = (pick in x['gold_set']) if x.get('gold_set') else (pick == x['gold'])
        by_type_tot[x['type']] += 1
        by_type_ok[x['type']] += ok
        if not ok:
            bad.append({'idx': k, 'type': x['type'], 'gold': x['gold'], 'gold_set': x.get('gold_set'), 'pick': pick, 'q': x['q']})
    json.dump({'mismatch_idx': [b['idx'] for b in bad]}, open(os.path.join(HERE, 'fixtures', 'distill', f'verify_{pid}.json'), 'w'))
    report[pid] = {'questions': len(perm), 'answered': len(perm) - len(miss), 'missing': miss, 'agree': len(perm) - len(miss) - len(bad), 'mismatch': bad}
    print(pid, f"일치 {report[pid]['agree']}/{len(perm)} = {100 * report[pid]['agree'] / len(perm):.1f}% · 불일치 {len(bad)} · 빠짐 {len(miss)}")
tot = sum(r['questions'] for r in report.values())
agree = sum(r['agree'] for r in report.values())
print(f'합계 일치 {agree}/{tot} = {100 * agree / tot:.1f}%')
print('유형별 일치율:')
for t in sorted(by_type_tot, key=lambda t: by_type_ok[t] / by_type_tot[t]):
    print(f'  {t:24s} {by_type_ok[t]}/{by_type_tot[t]} = {100 * by_type_ok[t] / by_type_tot[t]:.1f}%')
json.dump({'by_persona': report, 'by_type': {t: [by_type_ok[t], by_type_tot[t]] for t in by_type_tot}}, open(os.path.join(HERE, 'results', 'distill_verify_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
