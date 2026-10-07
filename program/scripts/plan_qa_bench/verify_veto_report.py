# 「짧은 확인 질문」 검토자(FrogNano · 가르치기 전 E4B)의 YES 확률로 짚기 모델의 오지목을 거르는 오프라인 계산 — D(개발/시험 분할) · D2 · D3.
#  거르는 규칙: 짚기 모델이 항목을 골랐고 검토자의 p_yes < τ 이면 「없음」. 비교: 일정 전체를 다시 읽히는 거부권(FrogNano 가 같은 질의문으로 푼 답).
# 사용: python verify_veto_report.py  → results/verify_veto_report.md
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')
D = os.path.join(HERE, 'results', 'd_test')
E = os.path.join(HERE, 'results', 'empty_probe')


def jl(name):
    d = {}
    for line in open(os.path.join(D, name), encoding='utf-8'):
        r = json.loads(line)
        d[r.get('key', r.get('i'))] = r
    return d


V = {'FrogNano(짧은 확인)': jl('verify_frog.jsonl'), '가르치기 전 E4B(짧은 확인)': jl('verify_e4bbase.jsonl')}
SEEDS = {'시드 1': 'e4bt', '시드 2': 'e4bs2', '시드 3': 'e4bs3'}
SRC = {'D': ('d_test_lp_{}.jsonl', 'q4km_'), 'D2': ('d_test_lp_d2_{}.jsonl', 'q4km_'), 'D3': ('d_test_d3_{}.jsonl', 'q4km_')}
data = {}
for ds, (pat, pre) in SRC.items():
    for s, n in SEEDS.items():
        data[(ds, s)] = jl(pat.format(pre + n))
frogfull = {'D': jl('d_test_a_frognano.jsonl'), 'D2': jl('d_test_d2_frog.jsonl'), 'D3': jl('d_test_d3_frog.jsonl')}
P = {'D': {p['i']: p for p in json.load(open(os.path.join(E, 'all_prompts.json'), encoding='utf-8'))}}


def final(ds, s, i, verifier, tau):
    r = data[(ds, s)][i]
    p = r.get('pick')
    if p is None:
        return None
    if verifier == 'full':
        return None if frogfull[ds][i].get('pick') is None else p
    if verifier == 'none':
        return p
    v = V[verifier].get(f'{ds}|{i}|{p}')
    if v is None or v.get('p_yes') is None:
        return p
    return None if v['p_yes'] < tau else p


def metrics(ds, s, verifier, tau):
    ids = [i for i, r in data[(ds, s)].items() if r['type'] != 'compound_intent']
    nul = ans = fp = ok = 0
    for i in ids:
        g = data[(ds, s)][i]['gold']
        f = final(ds, s, i, verifier, tau)
        if g is None:
            nul += 1
            fp += f is not None
        else:
            ans += 1
            ok += f == g
    return (fp / nul if nul else None), (ok / ans if ans else None)


GRID = [0.5, 0.2, 0.1, 0.05, 0.02, 0.01]
out = ['# 짧은 확인 질문 검토자(고객 말 + 고른 항목 한 줄)로 거르기 — 서비스 기반 Q4_K_M 시드 1·2·3, D · D2 · D3\n',
       '표의 값: 오지목 % / 정답 있는 질문 % (시드 1 · 2 · 3 순서). D2 는 잡담뿐이라 오지목만, 정답 있는 질문은 D · D3.\n',
       '| 검토 방식 | 문턱 p_yes < τ | D 오지목 / 정답 있는 질문 | D2 잡담 오지목 | D3 오지목 / 정답 있는 질문 |', '|---|---|---|---|---|']


def cell(ds, verifier, tau, with_ans=True):
    r = [metrics(ds, s, verifier, tau) for s in SEEDS]
    if with_ans:
        return ' · '.join(f'{100 * x[0]:.1f}/{100 * x[1]:.1f}' for x in r)
    return ' · '.join(f'{100 * x[0]:.1f}' for x in r)


out.append(f"| 거르지 않음 | — | {cell('D', 'none', 0, True)} | {cell('D2', 'none', 0, False)} | {cell('D3', 'none', 0, True)} |")
out.append(f"| FrogNano 일정 전체(앞의 거부권) | — | {cell('D', 'full', 0, True)} | {cell('D2', 'full', 0, False)} | {cell('D3', 'full', 0, True)} |")
for vname in V:
    for tau in GRID:
        out.append(f"| {vname} | {tau:g} | {cell('D', vname, tau, True)} | {cell('D2', vname, tau, False)} | {cell('D3', vname, tau, True)} |")
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'verify_veto_report.md'), 'w', encoding='utf-8').write(text)
print(text)
