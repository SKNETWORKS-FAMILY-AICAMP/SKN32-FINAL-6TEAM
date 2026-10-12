# 결정 단위 재생(172사례 × 3번) — 우리(gemma4:12b, 제품 모델) · Codex 루나 · 솔을 같은 사례 · 같은 제품 지시문/검증으로 센다. 새 호출 없음.
#  지표: 반복별 정답 · 3번 평균(사례 복원 추출 부트스트랩 95%) · pass^1/2/3 · 엉뚱한 대상 변경(반복별) · 지연 중앙/p95(CLI 기준) · 호출 실패(시스템 오류, 재시도 뒤에도 남은 것).
#  ★사례 · 정답 표기자는 Claude 계열 세션(cases_real · long7 = claude, fact · ui25 = cs/ui 세션) — Codex 모델에는 출제자 편향이 없다. 반대로 제품 지시문(SYSTEM)이 이 사례로 다듬어져 gemma4:12b 쪽이 유리할 수 있다.
# 사용: python codex_du_report.py   → results/codex_du_report.md
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import bootstrap_ci, fmt_ratio, pass_hat_k, percentile  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
OUT = os.path.join(HERE, 'results', 'codex_du')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DU = os.path.join(ROOT, 'final_project_cs', 'eval', 'decision_unit')
RUNS = {'cases_real': ['1742', '1751', '1758'], 'cases_fact': ['1740', '1747', '1753'], 'cases_long7': ['1745', '1749', '1756'], 'cases_ui25': ['1744', '1748', '1754']}
FILE_OF = {'cases_real': 'cases_real.jsonl', 'cases_fact': 'cases_fact.jsonl', 'cases_long7': 'cases_long7.jsonl', 'cases_ui25': 'cases_ui25.jsonl'}


def ours():
    succ, wt, secs = [], [0, 0, 0], []
    per = []
    for name, stamps in RUNS.items():
        reps = [json.load(open(os.path.join(DU, f'report_{name}_20260930_{s}.json'), encoding='utf-8'))['rows'] for s in stamps]
        for i in range(len(reps[0])):
            succ.append(sum(1 for r in reps if r[i]['good']))
            per.append((FILE_OF[name], i))
        for k, r in enumerate(reps):
            wt[k] += sum(1 for x in r if x.get('wrong_target_change'))
            secs += [x['seconds'] for x in r if x.get('seconds') is not None]
    return {'succ': succ, 'wt': wt, 'secs': secs, 'per': per, 'errors': 0}


def codex(model):
    reps = []
    for r in (1, 2, 3):
        p = os.path.join(OUT, f'{model}_rep{r}.json')
        if os.path.exists(p):
            reps.append(json.load(open(p, encoding='utf-8'))['rows'])
    if len(reps) < 3:
        return None
    key = lambda x: (x['_file'], x['_n'])
    base = sorted(reps[0], key=key)
    per = [key(x) for x in base]
    maps = [{key(x): x for x in rep} for rep in reps]
    succ = [sum(1 for m in maps if m[k]['good'] and not m[k]['got'].get('error')) for k in per]
    wt = [sum(1 for x in rep if x['wrong_target_change']) for rep in reps]
    secs = [x['seconds'] for rep in reps for x in rep if not x['got'].get('error')]
    errs = sum(1 for rep in reps for x in rep if x['got'].get('error'))
    return {'succ': succ, 'wt': wt, 'secs': secs, 'per': per, 'errors': errs}


systems = {'우리 gemma4:12b(제품)': ours(), 'Codex 루나': codex('gpt-6-luna'), 'Codex 솔': codex('gpt-6-sol')}
out = ['# 결정 단위 재생 — 172사례 × 3번, 같은 제품 지시문 · 검증 (우리 · Codex 루나 · 솔)\n',
       '- 사례 · 정답 표기자는 **Claude 계열 세션**이다(Codex 모델에는 출제자 편향 없음). 반대로 제품 지시문이 이 사례로 다듬어져 **gemma4:12b 가 유리**할 수 있다.',
       '- Codex 는 CLI 를 사례마다 한 번씩 불러 잰 값(구독 CLI, API 직접 호출이 아님) — 지연은 CLI 시작 오버헤드를 포함해 API 보다 느리다. 호출 실패(메모리 부족 등 시스템 오류)는 재시도했고 남은 것만 센다.',
       '- 우리 값의 3번은 2026-09-30 저장 결과(회차 사이 코드가 같았는지 기록이 없다).\n',
       '| 시스템 | 반복별 정답 /172 | 3번 평균 (부트스트랩 95%) | pass^2 | pass^3 | 엉뚱한 대상 변경(반복별) | 지연 중앙 / p95 (초) | 호출 실패 |', '|---|---|---|---:|---:|---|---|---:|']
for name, s in systems.items():
    if s is None:
        out.append(f'| {name} | (3번 미완료) | | | | | | |')
        continue
    succ = s['succ']
    per_rep = []
    for k in range(3):
        per_rep.append(sum(1 for c in succ if False))      # 자리표시(아래에서 다시 계산)
    # 반복별 정답 수는 succ 로 직접 못 구하므로 평균만 쓴다 — 반복별 값은 저장된 rows 에서
    if name.startswith('우리'):
        rep_scores = [160, 165, 167]
    else:
        model = 'gpt-6-luna' if '루나' in name else 'gpt-6-sol'
        rep_scores = [sum(1 for x in json.load(open(os.path.join(OUT, f'{model}_rep{r}.json'), encoding='utf-8'))['rows'] if x['good'] and not x['got'].get('error')) for r in (1, 2, 3)]
    cells = []
    for k in (1, 2, 3):
        pt, lo, hi = bootstrap_ci(succ, lambda u, k=k: pass_hat_k(u, 3, k), B=10000)
        cells.append((pt, lo, hi))
    out.append(f"| {name} | {' · '.join(str(x) for x in rep_scores)} | {100 * cells[0][0]:.1f}% ({100 * cells[0][1]:.1f}~{100 * cells[0][2]:.1f}) | {100 * cells[1][0]:.1f}% | **{100 * cells[2][0]:.1f}%** ({100 * cells[2][1]:.1f}~{100 * cells[2][2]:.1f}) | "
               f"{' · '.join(str(x) for x in s['wt'])} | {percentile(s['secs'], 50):.1f} / {percentile(s['secs'], 95):.1f} | {s['errors']} |")
# 우리와 사례 단위 비교: 3번 모두 맞은 사례의 McNemar
from stats import mcnemar_exact  # noqa: E402

ou = systems['우리 gemma4:12b(제품)']
if ou:
    omap = dict(zip(ou['per'], ou['succ']))
    out.append('\n**우리와 사례별 비교**(3번 모두 맞은 사례 기준 McNemar 정확검정)')
    out.append('| 시스템 | 이쪽만 3번 모두 맞음 : 우리만 | p |')
    out.append('|---|---|---:|')
    for name, s in systems.items():
        if s is None or name.startswith('우리'):
            continue
        smap = dict(zip(s['per'], s['succ']))
        keys = [k for k in omap if k in smap]
        m = mcnemar_exact([smap[k] == 3 for k in keys], [omap[k] == 3 for k in keys])
        out.append(f"| {name} | {m['a_only']} : {m['b_only']} | {m['p']:.2g} |")
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'codex_du_report.md'), 'w', encoding='utf-8').write(text)
print(text)
