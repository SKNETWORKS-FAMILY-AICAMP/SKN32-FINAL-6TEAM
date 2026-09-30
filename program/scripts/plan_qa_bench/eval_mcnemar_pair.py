# 같은 문제에서 두 「모델」의 직접 짚기끼리(또는 종단끼리) 다르게 맞힌 수와 정확 이항 검정 p — eval_mcnemar.py 가 「종단 대 직접」만 비교하는 한계를 메운다.
# 사용: python eval_mcnemar_pair.py <모델A> <모델B>   (이름은 eval_night.py 의 G 키: gemma4:e4b, gemma4:e4b-it-qat, var_gemma4:e2b|sfx …)
import contextlib, importlib.util, io, math, sys
A, B = sys.argv[1], sys.argv[2]
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    spec = importlib.util.spec_from_file_location('en', 'eval_night.py')
    en = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(en)


def p_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


for kind in ('직접', '종단'):
    tot = [0, 0, 0, 0]
    print(f'## {kind}: {A} 대 {B}')
    for j in ('heavy', 'mix4', 'mix5'):
        qs = en.SETS[j]['qs']
        idx = en.IDX[j]
        if kind == '직접':
            pa = {i: en.G[j][A][i] for i in idx}
            pb = {i: en.G[j][B][i] for i in idx}
        else:
            pa = {i: en.run(j, i, 0.25, 0.6, A)[0] for i in idx}
            pb = {i: en.run(j, i, 0.25, 0.6, B)[0] for i in idx}
        both = sum(pa[i] == qs[i]['gold'] and pb[i] == qs[i]['gold'] for i in idx)
        a_only = sum(pa[i] == qs[i]['gold'] and pb[i] != qs[i]['gold'] for i in idx)
        b_only = sum(pa[i] != qs[i]['gold'] and pb[i] == qs[i]['gold'] for i in idx)
        neither = len(idx) - both - a_only - b_only
        tot = [t + v for t, v in zip(tot, (both, a_only, b_only, neither))]
        print(f'  {j:6} 둘 다 맞음 {both} · A만 {a_only} · B만 {b_only} · 둘 다 틀림 {neither} → p={p_exact(a_only, b_only):.2f}')
    print(f'  합계   둘 다 맞음 {tot[0]} · A만 {tot[1]} · B만 {tot[2]} · 둘 다 틀림 {tot[3]} → p={p_exact(tot[1], tot[2]):.3f}')
