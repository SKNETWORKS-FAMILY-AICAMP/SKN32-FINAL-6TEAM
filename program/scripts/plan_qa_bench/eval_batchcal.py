# 배치 보정(yok3x 세션 43-4 의 방법) 이식 시험 — 앞단(학습 임베딩) 점수에서 「항목마다 평균적으로 높게 나오는 쏠림」을 빼 준다(라벨 0개, α 하나).
#  같은 일정(세트) 안의 모든 질문에 대한 항목별 평균 점수 m_i 를 구해 s'_i = s_i − α·(m_i − 전체평균) 으로 바꾼다. 점수의 전체 수준은 유지된다.
#  사전 등록(결과를 보기 전): α=1.0 하나가 주 결과, α=0.5 는 보조. 문턱 lo·hi 는 eval_night.py 와 같은 방식으로 heavy 개발용 44로만 고른다.
#  주의: 세트의 질문 중에는 「정답 없음」 문제가 섞여 있어 m_i 가 조금 부풀 수 있다(그 질문의 최고 점수도 평균에 들어간다).
# 사용: python eval_batchcal.py [넘김 모델 ...]
import contextlib, io, os, sys
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
names = sys.argv[1:] or ['gemma4:e4b-it-qat', 'gemma4:e4b', 'gemma4:26b']
src = open(os.path.join(HERE, 'eval_night.py'), encoding='utf-8').read()
head = src[:src.index('rows = []')]
ns = {'__name__': 'en', '__file__': os.path.join(HERE, 'eval_night.py')}
bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'eval_night_head', 'exec'), ns)
sys.argv = bak
S, SETS, IDX, run, pipe, grid, dev = (ns[k] for k in ('S', 'SETS', 'IDX', 'run', 'pipe', 'grid', 'dev'))
ORIG = {k: dict(v) for k, v in S.items()}


def recal(alpha):
    S.clear()
    for k, v in ORIG.items():
        S[k] = dict(v)
    if alpha == 0:
        return
    for job in SETS:
        for kind in ('tt', 'excl'):
            keys = [k for k in ORIG if k[0] == f'{job}_{kind}']
            if not keys:
                continue
            m = defaultdict(list)
            for k in keys:
                for it, sc in ORIG[k].items():
                    m[it].append(sc)
            mi = {it: sum(v) / len(v) for it, v in m.items()}
            g = sum(mi.values()) / len(mi)
            for k in keys:
                S[k] = {it: sc - alpha * (mi[it] - g) for it, sc in ORIG[k].items()}


def front_top1():
    out = {}
    for job in SETS:
        qs = SETS[job]['qs']
        ok = tot = 0
        for i in IDX[job]:
            x = qs[i]
            if x['gold'] is None or x['history']:
                continue
            k, p = ns['top'](job, 'tt', i)
            ok += k == x['gold']
            tot += 1
        out[job] = (ok, tot)
    return out


print('## 배치 보정 — 앞단 단독(정답 있고 앞 대화 없는 문제 top-1) + 종단(앞단+구조+넘김, 문턱은 heavy 개발용 44)')
print('| α | 앞단 top-1 heavy/mix4/mix5 | ' + ' | '.join(f'종단 합 264 ({n})' for n in names) + ' |')
print('|---|---|' + '---:|' * len(names))
for a in (0.0, 0.5, 1.0):
    recal(a)
    ft = front_top1()
    cells = []
    for n in names:
        best = max(grid, key=lambda g: (pipe('heavy', dev, *g, n)[0] - 2 * pipe('heavy', dev, *g, n)[1] - 0.05 * pipe('heavy', dev, *g, n)[2], -g[0]))
        tot = [pipe(j, IDX[j], *best, n) for j in SETS]
        cells.append(f"{sum(t[0] for t in tot)} (엉뚱 {sum(t[1] for t in tot)}, 호출 {sum(t[2] for t in tot)}, lo/hi {best[0]}/{best[1]})")
    print(f"| {a} | {ft['heavy'][0]}/{ft['heavy'][1]} · {ft['mix4'][0]}/{ft['mix4'][1]} · {ft['mix5'][0]}/{ft['mix5'][1]} | " + ' | '.join(cells) + ' |')
