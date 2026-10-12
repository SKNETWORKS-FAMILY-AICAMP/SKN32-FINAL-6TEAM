# [탐색·사후] 앞단 「없음」 문턱 lo 를 낮추면(점수가 낮은 문제를 「없음」으로 닫지 않고 넘김 모델에 넘기면) mix6 에서 어떻게 달라지나.
#  mix6 결과를 본 뒤의 분석이라 사전 지정 결과가 아니다 — 새 독립 세트에서 다시 확인하기 전에는 기준 구성을 바꾸지 않는다.
import contextlib, io, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'eval_mix6.py'), encoding='utf-8').read()
head = src[:src.index("gold = [x['gold'] for x in qs]")]
ns = {'__name__': 'em', '__file__': os.path.join(HERE, 'eval_mix6.py')}
bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'em_head', 'exec'), ns)
sys.argv = bak
SETS, run, IDX = ns['SETS'], ns['run'], ns['ns']['IDX']
M = 'gemma4:e4b-it-qat'
print('| lo | 기존 264 정답/엉뚱/호출 | mix6 130 정답/엉뚱/호출 | 합 394 정답 |')
print('|---|---|---|---:|')
for lo in (0.0, 0.05, 0.10, 0.15, 0.20, 0.25):
    row = []
    tot = 0
    for name, sets in (('old', ['heavy', 'mix4', 'mix5']), ('mix6', ['mix6'])):
        ok = bad = calls = 0
        for j in sets:
            idx = IDX[j] if j != 'mix6' else range(len(SETS['mix6']['qs']))
            for i in idx:
                p, used = run(j, i, lo, 0.6, M)
                g = SETS[j]['qs'][i]['gold']
                ok += p == g
                bad += p is not None and p != g
                calls += used
        row.append((ok, bad, calls))
        tot += ok
    print(f"| {lo} | {row[0][0]}/{row[0][1]}/{row[0][2]} | {row[1][0]}/{row[1][1]}/{row[1][2]} | {sum(r[0] for r in row)} |")
