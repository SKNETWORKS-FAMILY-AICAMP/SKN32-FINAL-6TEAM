# 같은 문제에서 두 방식이 다르게 맞힌 수(대응 비교)와 정확 이항 검정 p 값 — 「동급」 주장의 통계적 의미를 확인한다.
#  방식 A = 학습 임베딩 0.6B + 구조 + 넘김 모델(기본 gemma4:e4b, 문턱 0.25/0.6) · 방식 B = Gemma 26B 직접.
# 사용: python eval_mcnemar.py [넘김 모델=gemma4:e4b] [비교 모델=gemma4:26b]
import contextlib, importlib.util, io, math, sys
FB = sys.argv[1] if len(sys.argv) > 1 else 'gemma4:e4b'
BASE = sys.argv[2] if len(sys.argv) > 2 else 'gemma4:26b'
sys.argv = ['x']
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    spec = importlib.util.spec_from_file_location('en', 'eval_night.py')
    en = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(en)


def p_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


tot = [0, 0, 0, 0]
print(f'A = 학습 임베딩 0.6B + 구조 + {FB}  대  B = {BASE} 직접')
for j in ('heavy', 'mix4', 'mix5'):
    qs = en.SETS[j]['qs']
    idx = en.IDX[j]
    a = [en.run(j, i, 0.25, 0.6, FB)[0] == qs[i]['gold'] for i in idx]
    b = [en.G[j][BASE][i] == qs[i]['gold'] for i in idx]
    both = sum(x and y for x, y in zip(a, b)); only_a = sum(x and not y for x, y in zip(a, b)); only_b = sum(y and not x for x, y in zip(a, b)); neither = len(idx) - both - only_a - only_b
    tot = [tot[0] + both, tot[1] + only_a, tot[2] + only_b, tot[3] + neither]
    print(f'  {j:<6} 둘 다 맞음 {both} · A만 맞음 {only_a} · B만 맞음 {only_b} · 둘 다 틀림 {neither}  → p={p_exact(only_a, only_b):.2f}')
print(f'  합계   둘 다 맞음 {tot[0]} · A만 맞음 {tot[1]} · B만 맞음 {tot[2]} · 둘 다 틀림 {tot[3]}  → p={p_exact(tot[1], tot[2]):.2f} (p 가 크면 차이가 우연과 구분되지 않는다)')
