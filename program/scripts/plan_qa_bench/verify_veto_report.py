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
for _f, _n in (('verify_g12b.jsonl', 'gemma4:12b(짧은 확인)'), ('verify_e4bq4km.jsonl', '가르치기 전 E4B Q4_K_M(짧은 확인)')):
    if os.path.exists(os.path.join(D, _f)):
        V[_n] = jl(_f)
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
# 잡담 부정 사례를 더해 다시 가르친 oos1 — 검토자가 oos1 이 고른 답에도 더 줄일 여지가 있는지(검토 결과가 있는 FrogNano · gemma4:12b 만)
if os.path.exists(os.path.join(D, 'd_test_lp_q4km_oos1.jsonl')):
    for ds, (pat, pre) in SRC.items():
        data[(ds, 'oos1')] = jl(pat.format(pre + 'oos1'))
    out.append('\n## oos1(잡담 부정 사례를 더해 다시 가르친 E4B) + 짧은 확인 검토\n')
    out.append('표의 값: 오지목 % / 정답 있는 질문 %. 검토 결과가 없는 항목(검토를 못 받은 답)은 그대로 둔다 — 아래에 그 수를 함께 적는다.\n')
    out.append('| 검토 방식 | τ | D | D2(오지목만) | D3 |')
    out.append('|---|---|---|---|---|')

    def one(ds, verifier, tau, with_ans=True):
        x = metrics(ds, 'oos1', verifier, tau)
        return f'{100 * x[0]:.1f}/{100 * x[1]:.1f}' if with_ans else f'{100 * x[0]:.1f}'
    out.append(f"| 거르지 않음 | — | {one('D', 'none', 0)} | {one('D2', 'none', 0, False)} | {one('D3', 'none', 0)} |")
    for vname in ('FrogNano(짧은 확인)', 'gemma4:12b(짧은 확인)'):
        if vname not in V:
            continue
        for tau in GRID:
            out.append(f"| {vname} | {tau:g} | {one('D', vname, tau)} | {one('D2', vname, tau, False)} | {one('D3', vname, tau)} |")
    miss = {}
    for vname in ('FrogNano(짧은 확인)', 'gemma4:12b(짧은 확인)'):
        if vname in V:
            miss[vname] = sum(1 for ds in SRC for i, r in data[(ds, 'oos1')].items() if r.get('pick') is not None and r['type'] != 'compound_intent' and V[vname].get(f'{ds}|{i}|{r["pick"]}') is None)
    out.append('\n- 검토 못 받은 답(oos1 이 항목을 골랐는데 검토 결과가 없는 건수): ' + ' · '.join(f'{k} {v}' for k, v in miss.items()))
text = '\n'.join(out)
open(os.path.join(HERE, 'results', 'verify_veto_report.md'), 'w', encoding='utf-8').write(text)
print(text)
