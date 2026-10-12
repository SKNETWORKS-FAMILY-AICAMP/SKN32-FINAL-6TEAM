# D 시험(혼합 트래픽 2,735문제) 결과 모음 — 같은 조건(생각 끔, 요청 둘 제외 2,669문제, 엄격 계수: 빈 답·읽기 실패는 오답)으로 모델마다 센다.
#  지표: 전체 정답 · 빈 답 · 정답이 「없음」인 질문에서 항목을 짚음(오지목률) · 정답 항목이 있는 질문 정확도 · 지연 중앙/p95. 기준 = 가르친 E4B 단독(생각 끔, 서버 B llama.cpp Q8): 짝지은 McNemar.
# 사용: python d_test_report.py <이름=결과.jsonl> [<이름=결과.jsonl> …]   → results/d_test/d_test_report.md
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'eval_kit'))
from stats import fmt_ratio, mcnemar_exact, percentile  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
RES = os.path.join(ROOT, 'datasets', 'travel', 'mixed_testset', 'results')
OUT = os.path.join(HERE, 'results', 'd_test')
os.makedirs(OUT, exist_ok=True)
base_rows = {}
for f in glob.glob(os.path.join(RES, 'empty_fix', 'fix_out_*.jsonl')):
    for line in open(f, encoding='utf-8'):
        r = json.loads(line)
        base_rows[(r['set'], str(r['qi']))] = r
old = json.load(open(os.path.join(RES, 'chain_mixedraw_e4b_only.json'), encoding='utf-8'))
meta = {(t['set'], str(t['qi'])): (t['type'], t['gold']) for t in old}


def load(path):
    d = {}
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        d[(r['set'], str(r['qi']))] = r
    return d


def judge(d):
    """키 → (정답?, 빈 답?, 짚은 번호) — 요청 둘 제외."""
    out = {}
    for k, (typ, gold) in meta.items():
        if typ == 'compound_intent' or k not in d:
            continue
        r = d[k]
        empty = ('error' in r) or (not r.get('parsed'))
        pick = None if empty else r['pick']
        out[k] = (pick == gold and not empty, empty, pick, gold)
    return out


systems = {'가르친 E4B 단독(생각 끔, llama.cpp GGUF Q8) — 기준': judge(base_rows)}
for arg in sys.argv[1:]:
    name, path = arg.split('=', 1)
    systems[name] = judge(load(path))
base = systems[next(iter(systems))]
out = ['# D 시험 — 혼합 트래픽 2,735문제(요청 둘 제외 2,669, 엄격 계수, 생각 끔) 모델별\n']
out.append('| 모델 | 채점한 문제 | 전체 정답 (Wilson 95%) | 빈 답 | 정답이 「없음」인 질문 → 항목을 짚음(오지목률) | 정답 항목이 있는 질문 정확도 | 기준 대비(이쪽만 : 기준만, p) |')
out.append('|---|---:|---|---:|---|---|---|')
for name, j in systems.items():
    keys = list(j)
    ok = [j[k][0] for k in keys]
    empty = sum(1 for k in keys if j[k][1])
    none_q = [k for k in keys if j[k][3] is None]
    item_q = [k for k in keys if j[k][3] is not None]
    leak = sum(1 for k in none_q if j[k][2] is not None)
    acc = sum(1 for k in item_q if j[k][0])
    cmp_ = '—'
    if j is not base:
        common = [k for k in keys if k in base]
        m = mcnemar_exact([j[k][0] for k in common], [base[k][0] for k in common])
        cmp_ = f"{m['a_only']} : {m['b_only']}, p={m['p']:.3g}"
    out.append(f'| {name} | {len(keys)} | {fmt_ratio(sum(ok), len(ok))} | {empty} | {fmt_ratio(leak, len(none_q))} | {fmt_ratio(acc, len(item_q))} | {cmp_} |')
out.append('\n- 한계: 합성 문제 · 1회 · 모델마다 실행기(llama.cpp / Ollama)와 양자화가 달라 순위가 아니라 「같은 문제에서의 값」이다. 가르친 모델은 학습 자료와 같은 합성 분포라 낙관적이다.')
text = '\n'.join(out)
open(os.path.join(OUT, 'd_test_report.md'), 'w', encoding='utf-8').write(text)
print(text)
