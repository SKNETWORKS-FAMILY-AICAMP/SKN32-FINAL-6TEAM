# V14(§48) — 앞단 문턱(lo·hi)을 heavy 개발용 44문제가 아니라 기존 5세트 전체(heavy 판정 88 포함 567문제)에서 고른다. 단위 = 정답 − 2×엉뚱한 답 − 0.05×호출, 동점이면 lo 큰 쪽.
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
argv0 = sys.argv
sys.argv = ['x', 'e16d']
src = open(os.path.join(HERE, 'eval_router.py'), encoding='utf-8').read()
head = src[:src.index('# 문턱(개발용 44 로 선택)')]
G0 = {'__name__': 'er', '__file__': os.path.join(HERE, 'eval_router.py')}
exec(compile(head, 'er', 'exec'), G0)
sys.argv = argv0
SETS, run, grid, LABELED, M, pipe, dev = (G0[k] for k in ('SETS', 'run', 'grid', 'LABELED', 'M', 'pipe', 'dev'))
idx = {w: [i for i in range(len(SETS[w]['qs'])) if not (w == 'heavy' and SETS[w]['qs'][i].get('split') != 'held')] for w in LABELED}
grid = [(lo_, hi_) for lo_ in (0.0, 0.05, 0.10, 0.15, 0.20, 0.25) for hi_ in (0.6, 0.65, 0.7, 0.75)]   # 낮은 lo 를 포함하도록 격자를 넓혔다(기존 격자는 lo 0.15 가 하한)
print('격자', sorted({g[0] for g in grid}), sorted({g[1] for g in grid}))
rows = []
for lo, hi in grid:
    ok = bad = calls = 0
    for w in LABELED:
        for i in idx[w]:
            p, u = run(w, i, lo, hi, M)
            g = SETS[w]['qs'][i]['gold']
            ok += p == g
            bad += p is not None and p != g
            calls += u
    rows.append((ok - 2 * bad - 0.05 * calls, lo, hi, ok, bad, calls))
rows.sort(key=lambda r: (-r[0], -r[1]))
print('상위 8:')
for r in rows[:10]:
    print(f'  단위 {r[0]:.1f} · lo {r[1]} hi {r[2]} → 정답 {r[3]} 엉뚱 {r[4]} 호출 {r[5]}')
cur = [r for r in rows if (r[1], r[2]) == (0.15, 0.7)]
print('현재(0.15/0.7):', cur)
print('최선(5세트 전체):', rows[0][1:3])
