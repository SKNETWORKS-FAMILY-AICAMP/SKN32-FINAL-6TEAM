# Codex 재순위기 · 판정기 결과(codex_rerank_run.py)를 우리 재순위안(gemma4:12b, V7c — 후보 20)과 같은 지표로 센다. 새 호출 없음(우리 쪽은 exp5 캐시).
#  지표: 답 있음 질문의 Recall@3(모델이 고른 줄을 앞에 놓고 나머지는 1단계 순서) · 고객에게 보이는 줄(고른 줄 중 앞 2개, 색인 E 점수 0.45 이상) 안의 정답 · 답 없는 질문에 보임 · 근접·부분 답에 보임. 모두 Wilson 95%.
# 사용: python codex_rerank_eval.py   → ../results/rag_improve/codex_rerank_eval.md
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'eval_kit'))
from rerank_lib import llm_rank, load_cache  # noqa: E402
from stats import fmt_ratio, mcnemar_exact  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
OUT = os.path.abspath(os.path.join(HERE, '..', 'results', 'rag_improve'))
D = json.load(open(os.path.join(OUT, 'ce_input.json'), encoding='utf-8'))
CACHE = load_cache()
GATE = 0.45


def ours(sname):
    return {str(k): {'picks': llm_rank('gemma4:12b', r['q'], r['cand'][:20], CACHE)} for k, r in enumerate(D['sets'][sname])}


systems = {'우리 현재안 gemma4:12b 재순위기(후보 20)': {'B': ours('B'), 'H': ours('H')}}
for model in ('gpt-6-luna', 'gpt-6-sol'):
    for role in ('rerank', 'judge'):
        p = os.path.join(OUT, f'codex_{role}_{model}.json')
        if os.path.exists(p):
            systems[f'{model} {"재순위기(후보 20)" if role == "rerank" else "판정기(후보 5)"}'] = json.load(open(p, encoding='utf-8'))


def metrics(sname, sysres):
    rows = D['sets'][sname]
    n = r3 = sh = 0
    neg = leak = nm = nms = err = 0
    flags = {}
    for k, r in enumerate(rows):
        v = sysres.get(sname, {}).get(str(k))
        if v is None or 'error' in v:
            err += 1
            continue
        picks = v['picks']
        full = picks + [c for c in r['cand'] if c not in picks]
        se = dict(zip(r['cand'], r['se']))
        shown = [c for c in picks[:3] if se.get(c, 0) >= GATE][:2]
        if r['type'] == 'answerable':
            n += 1
            g = set(r['gold'])
            ok = bool(g & set(full[:3]))
            r3 += ok
            sh += bool(g & set(shown))
            flags[k] = ok
        elif r['type'] in ('uncovered', 'offtopic'):
            neg += 1
            leak += bool(shown)
        elif r['type'] == 'near_miss':
            nm += 1
            nms += bool(shown)
    return {'n': n, 'r3': r3, 'sh': sh, 'neg': neg, 'leak': leak, 'nm': nm, 'nms': nms, 'err': err, 'flags': flags}


out = ['# 규정 검색 — Codex(루나 · 솔)를 재순위기 · 판정기로 쓴 값 vs 우리 재순위안 (같은 1단계 후보, 같은 질문, 후보 20 · 판정은 상위 5)\n']
out.append('- 보이는 줄 = 모델이 고른 줄 중 앞 2개 가운데 색인 E 점수 0.45 이상. ★B 는 Codex(gpt-6-sol)가 쓴 질문이라 Codex 모델에 출제자 편향이 있다 — **H(Claude 작업자 작성) 를 주 비교**로 읽는다.')
for sname, title in (('H', '보류 세트 H(답 있음 68 · 답 없음 47 · 근접·부분 25) — 주 비교'), ('B', '독립 세트 B(답 있음 48 · 답 없음 50 · 근접·부분 62) — Codex 출제자 편향 있음')):
    out.append(f'\n## {title}\n')
    out.append('| 시스템 | Recall@3 | 보이는 줄에 정답 | 답 없는 질문에 보임(새어 나감) | 근접·부분 답에 보임 | 호출 실패 |')
    out.append('|---|---|---|---|---|---:|')
    base = None
    for name, res in systems.items():
        m = metrics(sname, res)
        if base is None:
            base = m
        cmp_ = ''
        if m is not base and m['flags'] and len(m['flags']) == len(base['flags']):
            c = mcnemar_exact([m['flags'][k] for k in base['flags']], [base['flags'][k] for k in base['flags']])
            cmp_ = f" (우리와 {c['a_only']} : {c['b_only']}, p={c['p']:.2g})"
        out.append(f"| {name} | {fmt_ratio(m['r3'], m['n'])}{cmp_} | {fmt_ratio(m['sh'], m['n'])} | {fmt_ratio(m['leak'], m['neg'])} | {m['nms']}/{m['nm']} | {m['err']} |")
text = '\n'.join(out)
open(os.path.join(OUT, 'codex_rerank_eval.md'), 'w', encoding='utf-8').write(text)
print(text)
