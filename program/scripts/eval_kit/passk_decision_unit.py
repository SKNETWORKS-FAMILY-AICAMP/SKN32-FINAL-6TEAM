# 결정 단위 재생 시험의 일관성(pass^k) — 같은 사례를 3번 돌린 저장 결과(2026-09-30 17:40~17:58, 세트 4개 × 3회)에서 계산한다. 새 호출 없음.
#  pass^k(τ-bench, Yao 등 2024): 사례마다 n 번 시도해 c 번 맞았을 때 「k 번 모두 맞을」 확률의 비편향 추정 E[C(c,k)/C(n,k)]. pass^1 은 평균 정답률, k 가 커질수록 신뢰성(매번 맞는가)을 본다.
#  구간: 사례를 복원 추출하는 부트스트랩 95%(B=10,000). 3번의 실행이 같은 코드·같은 모델이었는지는 저장 기록에 없다(확인 못 함).
# 사용: python passk_decision_unit.py  → results/passk_decision_unit.txt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DU = os.path.join(ROOT, 'final_project_cs', 'eval', 'decision_unit')
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8')
from stats import bootstrap_ci, pass_hat_k  # noqa: E402

RUNS = {'cases_real': ['1742', '1751', '1758'], 'cases_fact': ['1740', '1747', '1753'], 'cases_long7': ['1745', '1749', '1756'], 'cases_ui25': ['1744', '1748', '1754']}
LAB = {'cases_real': '실제 대화', 'cases_fact': '사실 질문', 'cases_long7': '긴 대화', 'cases_ui25': '화면 조작'}
out = []
allc = []
out.append('# 결정 단위 재생 — 같은 사례 3회 반복의 일관성 (pass^k)\n')
out.append('| 세트 | 사례 수 | pass^1 | pass^2 | pass^3 | 3번 모두 틀린 사례 | 일부만 맞은 사례 |')
out.append('|---|---:|---:|---:|---:|---:|---:|')
for name, stamps in RUNS.items():
    reps = [json.load(open(os.path.join(DU, f'report_{name}_20260930_{s}.json'), encoding='utf-8'))['rows'] for s in stamps]
    n = len(reps[0])
    assert all(len(r) == n for r in reps)
    for i in range(n):
        assert reps[0][i]['message'] == reps[1][i]['message'] == reps[2][i]['message'], (name, i)
    succ = [sum(1 for r in reps if r[i]['good']) for i in range(n)]
    allc += succ
    cells = []
    for k in (1, 2, 3):
        point, lo, hi = bootstrap_ci(succ, lambda u, k=k: pass_hat_k(u, 3, k), B=10000)
        cells.append(f'{100 * point:.1f}% ({100 * lo:.1f}~{100 * hi:.1f})')
    zero = sum(1 for c in succ if c == 0)
    part = sum(1 for c in succ if 0 < c < 3)
    out.append(f'| {LAB[name]} | {n} | ' + ' | '.join(cells) + f' | {zero} | {part} |')
cells = []
for k in (1, 2, 3):
    point, lo, hi = bootstrap_ci(allc, lambda u, k=k: pass_hat_k(u, 3, k), B=10000)
    cells.append(f'{100 * point:.1f}% ({100 * lo:.1f}~{100 * hi:.1f})')
out.append(f'| **전체** | {len(allc)} | ' + ' | '.join(cells) + f' | {sum(1 for c in allc if c == 0)} | {sum(1 for c in allc if 0 < c < 3)} |')
out.append('\n- 칸의 괄호 = 부트스트랩 95% 구간. pass^3 은 「3번 모두 맞은 사례의 비율」에 가깝다(사례마다 c 가 3 일 때 1, 아니면 0).')
out.append('- pass^1 과 pass^3 의 차이가 클수록 같은 질문에 답이 흔들린다(생각 모드 · 확률적 생성). 이 시험의 생성은 온도 0 이지만 모델 서버가 완전히 결정적이지는 않다.')
out.append('- 한계: 사례의 정답은 Claude 가 표기했고 사람 검수가 없다. 세 번의 실행이 같은 코드였는지 기록이 없다.')
text = '\n'.join(out)
os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
open(os.path.join(HERE, 'results', 'passk_decision_unit.txt'), 'w', encoding='utf-8').write(text)
print(text)
